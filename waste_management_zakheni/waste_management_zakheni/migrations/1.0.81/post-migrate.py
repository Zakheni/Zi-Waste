"""Fix amend email template recipient and migrate legacy assigned state if any."""


def migrate(cr, version):
    cr.execute("""
        UPDATE mail_template mt
           SET email_to = '{{object.manager_email}}'
          FROM ir_model_data imd
         WHERE imd.model = 'mail.template'
           AND imd.module = 'waste_management_zakheni'
           AND imd.name = 'mail_tmpl_service_request_amend'
           AND imd.res_id = mt.id
    """)
