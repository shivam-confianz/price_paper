from odoo import api, fields, models

from odoo import models, fields, _
from odoo.exceptions import ValidationError


class WebsiteLoyaltyProgram(models.Model):
    _name = 'website.loyalty.program'
    _description = 'Website Loyalty Program'
    _rec_name = 'name'

    name = fields.Char(string='Loyalty Program Name', required=True)
    # available_on = fields.Selection([('sales', 'Sales'), ('website', 'Website')], string='Available On')
    available_on_sales = fields.Boolean(string='Sales')
    available_on_website = fields.Boolean(string='Website')
    no_of_points = fields.Integer(string='No of Points')
    dollar_spent = fields.Integer(string='Amount spent', default=0.0)
    minimum_order = fields.Integer(string='Minimum Order Value', default=0.0)
    maximum_points = fields.Integer(string='Maximum Points per Order')
    exclude_category_ids = fields.Many2many('product.public.category', string='Exclude Categories')
    only_category_ids = fields.Many2many('product.public.category', 'product_public_category_website_loyalty_rel',
                                         string='Only Categories')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id,
                                 readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id.id)
    bonus_rule_ids = fields.One2many('website.loyalty.bonus.rules', 'program_id')
    reward_message = fields.Char(compute='_compute_reward_message')

    # @api.depends('dollar_spent')
    # def _compute_no_of_points(self):
    #     for record in self:
    #         record.no_of_points = record.dollar_spent * 0.5

    @api.depends('dollar_spent', 'no_of_points')
    def _compute_reward_message(self):
        for record in self:
            record.reward_message = (
                f"If you spent <b><span style='color:red;'>{record.dollar_spent}$</span></b> per purchase, you will be rewarded with <b><span style='color:red;'>"
                f"{record.no_of_points}</span> points </b>.")

    @api.constrains('only_category_ids')
    def _check_unique_only_category_ids_per_program(self):
        for program in self:
            if program.only_category_ids:
                existing_programs = self.search([
                    ('id', '!=', program.id),
                    ('only_category_ids', 'in', program.only_category_ids.ids)
                ])
                if existing_programs:
                    raise ValidationError(
                        'The combination of selected categories must be unique for each Loyalty Program.')


class WebsiteLoyaltyBonusRules(models.Model):
    _name = 'website.loyalty.bonus.rules'
    _description = 'Loyalty Bonus Rules'

    program_id = fields.Many2one('website.loyalty.program', string='Loyalty Program')
    tier_id = fields.Many2one('website.loyalty.tier', string='Tier', required=True)
    bonus_percentage = fields.Integer(string='Bonus Percentage')
    order_value = fields.Integer(string='Order Value')

    @api.constrains('tier', 'order_value', 'program_id')
    def _check_unique_tier_order_value_per_program(self):
        for rule in self:
            existing_rule = self.search([
                ('program_id', '=', rule.program_id.id),
                ('tier_id', '=', rule.tier_id.id),
                ('order_value', '=', rule.order_value),
                ('id', '!=', rule.id)
            ])
            if existing_rule:
                raise ValidationError(
                    'The combination of Tier and Order Value must be unique within the same Loyalty Program.')



class WebsiteLoyaltyRedeemTier(models.Model):
    _name='website.loyalty.redeem.tier'

    tier_id = fields.Many2one('website.loyalty.tier', string='Tier', required=True)
    points_multiplier = fields.Float(string='Points Multiplier')
    rule_id = fields.Many2one('website.loyalty.redeem.rules')

class WebsiteLoyaltyRedeemRules(models.Model):
    _name = 'website.loyalty.redeem.rules'
    _description = 'Loyalty Redeem Rules'

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(default=False)
    minimum_order_redeem = fields.Integer(string='Minimum Order Value', default=0.0)
    maximum_points_redeem = fields.Integer(string='Points Multiplier')
    no_of_points = fields.Integer(string="No:of points equivalent to dollar")
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id.id)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id,
                                 readonly=True)
    redumption_product_id = fields.Many2one('product.product', string="Redemption product")

    tier_ids_main = fields.One2many('website.loyalty.redeem.tier','rule_id')

    @api.constrains('active')
    def _check_single_active_rule(self):
        if self.active:
            active_rules = self.search([
                ('id', '!=', self.id),
                ('active', '=', True)
            ])
            if active_rules:
                raise ValidationError('Only one redemption rule can be active at a time.')

    def redeem_points(self, sale_order, points):
        # Ensure the points are valid for redemption
        if points > self.maximum_points_redeem:
            raise ValueError("Points exceed maximum points redeemable.")

        # Calculate the value of the points
        points_value = self.no_of_points
        redemption_amount = points / points_value
        if sale_order.partner_id.partner_tier:
            main_line = self.tier_ids_main.search([('tier_id.name','=',sale_order.partner_id.partner_tier)])
            if main_line:
                redemption_amount = redemption_amount*main_line.points_multiplier
        # Add a redemption line to the sale order
        if self.redumption_product_id:
            sale_order.write({
                'order_line': [(0, 0, {
                    'product_id': self.redumption_product_id.id,
                    'name':_("Reward Product") + " - " +  self.redumption_product_id.name,
                    'price_unit': redemption_amount,
                    'product_uom_qty': -1,
                    'order_id': sale_order.id,
                    'tax_id': False,
                    'is_redemption_product':True,
                    # 'discount': redemption_amount,
                })]
            })

            # self.redumption_product_id.write({'sale_ok': False})

        return {
            'status': True,
            'amount': redemption_amount,
            'points': points
        }


        # # Deduct the redeemed points from the customer's total points
        # sale_order.partner_id.total_confirm_points -= points

    # def redeem_points(self, sale_order, points):
    #     # Ensure the points are valid for redemption
    #     if points > self.maximum_points_redeem:
    #         raise ValueError("Points exceed maximum points redeemable.")
    #
    #     # Calculate the value of the points
    #     points_value = self.no_of_points
    #     redemption_amount = points / points_value
    #     total_subtotal = sum(line.price_subtotal for line in sale_order.order_line)
    #
    #     # Calculate the discount based on the total subtotal and redemption percentage
    #     discount_amount = (total_subtotal * redemption_amount) / 100
    #
    #     # Add a redemption line to the sale order
    #     if self.redumption_product_id:
    #         sale_order.write({
    #             'order_line': [(0, 0, {
    #                 'product_id': self.redumption_product_id.id,
    #                 'name': self.redumption_product_id.name,
    #                 'price_unit': -discount_amount,
    #                 'product_uom_qty': 1,
    #                 'order_id': sale_order.id,
    #                 'tax_id': False,
    #                 'is_redemption_product': True,
    #                 # 'discount': redemption_amount,
    #             })]
    #         })
    #     return {
    #         'status': True,
    #         'amount': -discount_amount,
    #         'points': points
    #     }
    #
