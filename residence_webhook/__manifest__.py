
{
    "name": "Residence Webhook Integration",
    "version": "1.1",
    "author": "Residence / Odoo Integration",
    "depends": ["base", "sale", "product"],
    "data": [
        "security/ir.model.access.csv",
        "data/webhook_cron.xml",
        "views/webhook_event_views.xml"
    ],
    "installable": True,
    "application": True
}
