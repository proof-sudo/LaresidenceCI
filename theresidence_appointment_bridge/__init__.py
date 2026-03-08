from . import models


def post_init_hook(env):
    """
    Appelé automatiquement après l'installation du module.
    Synchronise toutes les réservations existantes et tous les espaces.
    """
    import logging
    _logger = logging.getLogger(__name__)

    pos_configs = env['pos.config'].sudo().search([('active', '=', True)])

    # 1. Créer/lier les appointment.type pour tous les espaces existants
    spaces = env['product.template'].search([
        ('x_tr_is_space', '=', True),
    ])
    _logger.info("[TR BRIDGE] post_init_hook : %s espace(s) à traiter", len(spaces))

    for space in spaces:
        if not space.x_tr_appointment_type_id:
            space._ensure_appointment_type()
        elif pos_configs:
            # Lier les types existants au POS s'ils ne le sont pas encore
            space.x_tr_appointment_type_id.sudo().write({
                'pos_config_ids': [(6, 0, pos_configs.ids)]
            })

    # 2. Créer les calendar.event pour toutes les réservations sans event
    reservations = env['sale.order'].search([
        ('x_tr_is_reservation', '=', True),
        ('x_tr_calendar_event_id', '=', False),
        ('x_tr_start_time', '!=', False),
        ('x_tr_end_time', '!=', False),
        ('x_tr_reservation_status', 'not in', ['CANCELLED', 'REJECTED']),
    ])
    _logger.info("[TR BRIDGE] post_init_hook : %s réservation(s) à synchroniser", len(reservations))

    for res in reservations:
        try:
            res._sync_create_calendar_event()
        except Exception as e:
            _logger.warning("[TR BRIDGE] Échec sync réservation %s : %s", res.x_tr_uuid, str(e))

    _logger.info("[TR BRIDGE] post_init_hook terminé.")
