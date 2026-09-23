# Constat — lien devis de réservation ↔ commande caisse ↔ facture

Base interrogée : production `proof-sudo-laresidenceci` et copie `demo2`, le 23/09/2026.
Source de référence pour le code standard : dépôt officiel Odoo, branche 19.0, module `pos_sale`.

Ce document ne contient que des constats. Aucune interprétation n'y est présentée comme un fait.

---

## 1. Ce qui est installé

| Module | Production | demo2 |
|---|---|---|
| `point_of_sale` | installé | installé |
| `pos_sale` | installé 19.0.1.1 | installé 19.0.1.1 |
| `sale` | installé | installé |
| `theresidence_api` | installé 19.0.4 | installé 19.0.4 |
| `laresidence_pos_compte_client` | **non installé** | installé 19.0.6 |
| `sale_renting_pos_bridge` | non installé | non installé |

`pos_sale` est le module standard qui fournit le bouton de chargement d'un devis en caisse.
Il est bien présent sur les deux bases.

## 2. La fonction n'a jamais servi

| Mesure | Production | demo2 |
|---|---|---|
| Commandes caisse | 615 | 534 |
| Devis / commandes de vente | 314 | 418 |
| Lignes de caisse rattachées à un devis | **0** | **0** |
| Devis ayant des lignes reprises en caisse | **0** | **0** |

Aucune commande de caisse n'a jamais été créée à partir d'un devis, sur aucune des deux bases.
Le scénario existe donc dans l'outil mais n'a pas encore été utilisé en exploitation.

Répartition des devis en production :

| État / facturation | Nombre |
|---|---|
| Confirmé, facturé | 84 |
| Confirmé, à facturer | 53 |
| Confirmé, rien à facturer | 33 |
| Brouillon | 129 |
| Annulé | 15 |

## 3. Ce que le standard fait déjà — vérifié dans le code

### 3.1 Le double débit est déjà empêché

`pos_sale` étend trois calculs de la ligne de vente et de la commande de vente :

- `_prepare_qty_invoiced` ajoute la quantité des lignes de caisse rattachées à la quantité
  déjà facturée de la ligne de vente ;
- `_compute_untaxed_amount_invoiced` ajoute le sous-total des lignes de caisse au montant
  déjà facturé ;
- `_compute_amount_to_invoice` et `_compute_amount_unpaid` retranchent les montants encaissés
  en caisse.

Conséquence constatée dans le code : dès qu'un devis est consommé en caisse, il bascule de
lui-même en « facturé » et ne réapparaît pas dans le reste à facturer. **Le client ne se
retrouve donc pas débiteur deux fois du seul fait du standard.**

### 3.2 En revanche la facture n'est pas rattachée au devis

Méthode standard `pos_sale`, reprise telle quelle :

```python
def _get_invoice_lines_values(self, line_values, pos_line, move_type):
    inv_line_vals = super()._get_invoice_lines_values(line_values, pos_line, move_type)
    if pos_line.sale_order_origin_id:
        origin_line = pos_line.sale_order_line_id
        inv_line_vals["name"] = origin_line.name
        origin_line._set_analytic_distribution(inv_line_vals)
    if self.config_id.down_payment_product_id == pos_line.product_id:
        inv_line_vals["is_downpayment"] = True
    return inv_line_vals
```

Elle recopie le libellé et la répartition analytique de la ligne de vente. Elle **ne renseigne
pas** `sale_line_ids` sur la ligne de facture.

Or le devis retrouve ses factures par ce seul chemin :

```python
@api.depends('order_line.invoice_lines')
def _get_invoiced(self):
    for order in self:
        invoices = order.order_line.invoice_lines.move_id.filtered(
            lambda r: r.move_type in ('out_invoice', 'out_refund'))
        order.invoice_ids = invoices
        order.invoice_count = len(invoices)
```

Constat : une facture émise depuis la caisse n'apparaît pas dans les factures du devis
d'origine. C'est exactement le manque décrit dans la demande.

### 3.3 Le piège à connaître avant de combler ce manque

Le calcul de base de la quantité facturée compte les lignes de facture rattachées :

```python
def _prepare_qty_invoiced(self):
    invoiced_qties = defaultdict(float)
    for line in self:
        for invoice_line in line._get_invoice_lines():
            ...
```

et `pos_sale` **ajoute par-dessus** la quantité des lignes de caisse, sans vérifier si la
commande de caisse a été facturée :

```python
def _prepare_qty_invoiced(self):
    invoiced_qties = super()._prepare_qty_invoiced()
    for sale_line in self:
        pos_lines = sale_line.sudo().pos_order_line_ids.filtered(
            lambda order_line: order_line.order_id.state not in ['cancel', 'draft'])
        invoiced_qties[sale_line] += sum(...)
```

Constat : si on se contente de renseigner `sale_line_ids` sur la facture issue de la caisse,
la même quantité est comptée deux fois — une fois par le standard `sale`, une fois par
`pos_sale`. Le devis afficherait alors une quantité facturée double.

Le même raisonnement vaut pour `_compute_untaxed_amount_invoiced`, qui ajoute lui aussi le
sous-total des lignes de caisse sans condition.

## 4. Ce qui reste à établir

- Comportement réel du bouton de chargement d'un devis dans l'interface de caisse : jamais
  utilisé sur ces bases, donc jamais observé ici.
- Cas d'un devis partiellement consommé en caisse.
- Cas d'un devis réglé en compte client, qui part ensuite dans la facture groupée.
