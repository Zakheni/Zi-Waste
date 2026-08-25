"""Copy existing Pastel codes onto Sage alias fields after install."""


def post_init_hook(env):
    cr = env.cr
    cr.execute("""
        UPDATE res_partner p
           SET sage_code = p.x_pastel_code
          FROM (
                SELECT MIN(id) AS id
                  FROM res_partner
                 WHERE COALESCE(x_pastel_code, '') <> ''
                 GROUP BY COALESCE(company_id, 0), x_pastel_code
          ) first
         WHERE p.id = first.id
           AND COALESCE(p.sage_code, '') = ''
    """)
    cr.execute("""
        UPDATE product_template p
           SET sage_code = p.x_pastel_item_code
          FROM (
                SELECT MIN(id) AS id
                  FROM product_template
                 WHERE COALESCE(x_pastel_item_code, '') <> ''
                 GROUP BY COALESCE(company_id, 0), x_pastel_item_code
          ) first
         WHERE p.id = first.id
           AND COALESCE(p.sage_code, '') = ''
    """)
    cr.execute("""
        UPDATE account_move m
           SET sage_doc_no = m.x_pastel_doc_no
          FROM (
                SELECT MIN(id) AS id
                  FROM account_move
                 WHERE COALESCE(x_pastel_doc_no, '') <> ''
                 GROUP BY COALESCE(company_id, 0), x_pastel_doc_no
          ) first
         WHERE m.id = first.id
           AND COALESCE(m.sage_doc_no, '') = ''
    """)
