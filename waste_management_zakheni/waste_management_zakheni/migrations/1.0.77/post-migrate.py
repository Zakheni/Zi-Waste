"""Migrate legacy assigned manifests to scheduled."""

def migrate(cr, version):
    cr.execute("""
        UPDATE waste_service_request
           SET state = 'scheduled'
         WHERE state = 'assigned'
    """)
