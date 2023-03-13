# -*- coding: utf-8 -*-

{
    "name" : "Equipment Product Stock",
    "author": "Edge Technologies",
    "version" : "16.0.1.0",
    "live_test_url":'',
    "images":['static/description/main_screenshot.png'],
    'summary': 'Product Equipment stock for products equipment manage stock for equipment product equipment inventory for products equipment manage inventory for equipment inventory product manage inventory for equipments.',
    "description": """
    
    Product equipment stock    
    """,
    "license" : "OPL-1",
    "depends" : ['base','stock','maintenance','hr'],
    "data": [
        'security/ir.model.access.csv',
        'security/equipment_product_security.xml',
        'views/product_template_view.xml',
        'views/stock_inventory.xml',
        'views/equipment.xml',

    ],
    "auto_install": False,
    "installable": True,
    "price": 45,
    "currency": 'EUR',
    "category" : "Warehouse",
    
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
