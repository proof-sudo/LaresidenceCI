import base64
import io
import logging
import socket
import struct

from PIL import Image

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# ESC/POS command constants
ESCPOS_INIT = b'\x1b\x40'             # ESC @ - Initialize printer
ESCPOS_CENTER = b'\x1b\x61\x01'       # ESC a 1 - Center alignment
ESCPOS_LEFT = b'\x1b\x61\x00'         # ESC a 0 - Left alignment
ESCPOS_RASTER = b'\x1d\x76\x30\x00'   # GS v 0 - Print raster bit image
ESCPOS_FEED = b'\x1b\x64\x05'         # ESC d 5 - Feed 5 lines
ESCPOS_CUT = b'\x1d\x56\x00'          # GS V 0 - Full cut
ESCPOS_CASHBOX = b'\x1b\x70\x00\x19\xfa'  # ESC p - Kick cash drawer

SOCKET_TIMEOUT = 2.0  # seconds (LAN printers connect in <100ms)

# Max rows per GS v 0 raster command. Many thermal printers have a limited
# raster buffer and garble output when a single command exceeds it. 128 is
# safe across virtually all ESC/POS printers.
RASTER_BAND_HEIGHT = 128

# Pre-computed byte inversion table: 0→255, 1→254, ..., 255→0
# Used to convert PIL's 0=black/1=white to ESC/POS's 1=black/0=white
_INVERT_TABLE = bytes(~i & 0xFF for i in range(256))


class PosDirectPrinterController(http.Controller):

    @http.route('/pos_direct_printer/print', type='jsonrpc', auth='user')
    def print_receipt(self, printer_ip, printer_port, image,
                      open_cashbox=False, order_name='', table_name=''):
        user = request.env.user
        ctx = self._log_context(order_name, table_name, user)
        try:
            printer_port = int(printer_port)
            data = bytearray()
            data += ESCPOS_INIT

            job_type = []
            if image:
                img_data = base64.b64decode(image)
                img = Image.open(io.BytesIO(img_data))
                data += self._build_escpos_raster(img)
                job_type.append('receipt')

            if open_cashbox:
                data += ESCPOS_CASHBOX
                job_type.append('cashbox')

            if not image and not open_cashbox:
                return {'success': True}

            self._send_to_printer(printer_ip, printer_port, bytes(data))
            _logger.info(
                'Print OK: %s → %s:%s (%d bytes) %s',
                '+'.join(job_type), printer_ip, printer_port,
                len(data), ctx,
            )
            return {'success': True}

        except socket.timeout:
            _logger.warning(
                'Printer timeout: %s:%s %s', printer_ip, printer_port, ctx,
            )
            return {'success': False, 'error': 'Connection timed out'}
        except ConnectionRefusedError:
            _logger.warning(
                'Printer connection refused: %s:%s %s', printer_ip, printer_port, ctx,
            )
            return {'success': False, 'error': 'Connection refused — is the printer on?'}
        except OSError as e:
            _logger.warning(
                'Printer network error: %s:%s — %s %s', printer_ip, printer_port, e, ctx,
            )
            return {'success': False, 'error': f'Network error: {e}'}
        except Exception as e:
            _logger.exception(
                'Print error: %s %s', e, ctx,
            )
            return {'success': False, 'error': str(e)}

    @http.route('/pos_direct_printer/test', type='jsonrpc', auth='user')
    def test_printer(self, printer_ip, printer_port):
        user = request.env.user
        try:
            printer_port = int(printer_port)
            data = bytearray()
            data += ESCPOS_INIT
            data += ESCPOS_CENTER
            data += b'\n'
            data += '================================\n'.encode()
            data += '       TEST RECEIPT\n'.encode()
            data += '================================\n'.encode()
            data += b'\n'
            data += 'Printer is working!\n'.encode()
            data += b'\n'
            data += f'IP: {printer_ip}:{printer_port}\n'.encode()
            data += '================================\n'.encode()
            data += ESCPOS_FEED
            data += ESCPOS_CUT
            self._send_to_printer(printer_ip, printer_port, bytes(data))
            _logger.info(
                'Printer test OK: %s:%s by %s (uid=%d)',
                printer_ip, printer_port, user.name, user.id,
            )
            return {'success': True}
        except Exception as e:
            _logger.warning(
                'Printer test failed: %s:%s — %s — user %s (uid=%d)',
                printer_ip, printer_port, e, user.name, user.id,
            )
            return {'success': False, 'error': str(e)}

    def _build_escpos_raster(self, img):
        """Convert a PIL Image to ESC/POS raster bit image bytes."""
        # Convert to monochrome
        img = img.convert('L')
        img = img.point(lambda x: 0 if x < 128 else 255, '1')

        width, height = img.size
        # Pad width to multiple of 8 (white pixels, no resampling)
        if width % 8 != 0:
            new_width = width + (8 - width % 8)
            padded = Image.new('1', (new_width, height), 1)
            padded.paste(img, (0, 0))
            img = padded
            width = new_width

        bytes_per_row = width // 8

        data = bytearray()
        data += ESCPOS_CENTER

        # PIL mode '1' tobytes(): packed MSB-first, 0=black 255=white
        # ESC/POS expects: 1=black, 0=white — invert via C-level lookup table
        raw = img.tobytes().translate(_INVERT_TABLE)

        # Split the image into horizontal bands — a single GS v 0 command
        # exceeding the printer's raster buffer produces garbled output on
        # long receipts.
        for y in range(0, height, RASTER_BAND_HEIGHT):
            band_h = min(RASTER_BAND_HEIGHT, height - y)
            start = y * bytes_per_row
            end = start + band_h * bytes_per_row
            data += ESCPOS_RASTER
            data += struct.pack('<HH', bytes_per_row, band_h)
            data += raw[start:end]

        data += ESCPOS_FEED
        data += ESCPOS_CUT
        return bytes(data)

    @staticmethod
    def _log_context(order_name, table_name, user):
        """Build a compact context string for log messages."""
        parts = []
        if order_name:
            parts.append(f'order={order_name}')
        if table_name:
            parts.append(f'table={table_name}')
        parts.append(f'{user.name} (uid={user.id})')
        return '— ' + ', '.join(parts)

    def _send_to_printer(self, ip, port, data):
        """Send raw bytes to printer via TCP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT)
        try:
            sock.connect((ip, port))
            sock.sendall(data)
        finally:
            sock.close()
