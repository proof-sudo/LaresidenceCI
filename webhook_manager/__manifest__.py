{
    "name": "Webhook Manager",
    "version": "1.1",
    "summary": "Gestion de webhooks pour envoyer les datas CRUD à une API externe",
    "author": "Votre Nom",
    "category": "Tools",
    "depends": [
        "base", "sale", "product", "pos_sale", "sale_subscription"
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/webhook_views.xml",
        "data/webhook_demo.xml"
    ],
    "installable": True,
    "application": False,
}
