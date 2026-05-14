from odoo import api, SUPERUSER_ID

def _seed_config_from_attributes(env):
    mapping = {
        'Service Requested': 'service.request',
        'Waste Type':        'waste.type',
        'Waste Details':     'waste.details',
        'Bin Type':          'bin.type',
        'Tank Volume':       'tank.volume',
        'Container Type':    'container.type',
    }
    PAV = env['product.attribute.value']
    for attr_name, model_name in mapping.items():
        for pav in PAV.search([('attribute_id.name', '=', attr_name)]):
            if not env[model_name].search([('pav_id', '=', pav.id)], limit=1):
                env[model_name].create({'pav_id': pav.id, 'name': pav.name})

def post_init_seed_waste_config(env):   # <-- env ONLY (Odoo 17 style)
    _seed_config_from_attributes(env)

