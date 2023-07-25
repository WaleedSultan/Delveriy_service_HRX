from odoo import api, fields, models, _
import base64
import logging

_logger = logging.getLogger(__name__)
from odoo.exceptions import  UserError


class ChooseDeliveryPackage(models.TransientModel):
    _inherit = "choose.delivery.package"

    length_hrx = fields.Float(string="Length")
    width_hrx = fields.Float(string="Width")
    height_hrx = fields.Float(string="Height")

    @api.onchange('delivery_package_type_id')
    def getting_len_wid_height(self):
        self.width_hrx = self.delivery_package_type_id.width
        self.height_hrx = self.delivery_package_type_id.height
        self.length_hrx = self.delivery_package_type_id.packaging_length


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(selection_add=[
        ('hrx', 'HRX'),
    ]
        , ondelete={'hrx': 'cascade'}
    )

    # delivery_type = fields.Selection(selection_add = [('wepik','Wepik')])
    hrx_product_group_id = fields.Many2one(comodel_name='hrx.product.group', string='HRX Product Group')
    hrx_product_type_id = fields.Many2one(comodel_name='hrx.product.type', string='HRX Product Type')
    hrx_payment_method_id = fields.Many2one(comodel_name='hrx.payment.method', string='HRX Payment Method')
    hrx_service_id = fields.Many2one(comodel_name='hrx.service', string='HRX Service')

    @api.model
    def create(self, vals):
        if vals.get("delivery_type", False) and vals["delivery_type"] == "hrx" and vals.get("uom_id", False):
            uom_obj = self.env["uom.uom"].browse(vals["uom_id"])
            if uom_obj and uom_obj.name.upper() not in ["LB", "LB(S)", "KG", "KG(S)"]:
                raise UserError(
                    _("HRX Shipping support weight in KG and LB only. Select Odoo Product UoM accordingly."))
        if vals.get("delivery_type", False) and vals["delivery_type"] == "hrx" and vals.get("delivery_uom", False):
            if vals["delivery_uom"] not in ["LB", "KG"]:
                raise UserError(_("HRX Shipping support weight in KG and LB only. Select API UoM accordingly."))
        return super(DeliveryCarrier, self).create(vals)

    def write(self, vals):
        for rec in self:
            if self.delivery_type == "hrx" and vals.get("uom_id", False):
                uom_obj = self.env["uom.uom"].browse(vals["uom_id"])
                if uom_obj and uom_obj.name.upper() not in ["LB", "LB(S)", "KG", "KG(S)"]:
                    raise UserError(
                        _("HRX Shipping support weight in KG and LB only. Select Odoo Product UoM accordingly."))
            if self.delivery_type == "hrx" and vals.get("delivery_uom", False):
                if vals["delivery_uom"] not in ["LB", "KG"]:
                    raise UserError(_("HRX Shipping support weight in KG and LB only. Select API UoM accordingly."))
        return super(DeliveryCarrier, self).write(vals)


class WkShippingProductType(models.Model):
    _name = "hrx.product.type"
    _description = "HRX product type"

    name = fields.Char(string="Name", required=1)
    code = fields.Char(string="Code", required=1)
    is_dutiable = fields.Boolean(string="Dutiable Product")
    description = fields.Text(string="Full Description")


class WkShippingService(models.Model):
    _name = "hrx.service"
    _description = "HRX Service"

    name = fields.Char(string="Name", required=1)
    code = fields.Char(string="Code", required=1)
    description = fields.Text(string="Full Description")


class WkShippingProductGroup(models.Model):
    _name = "hrx.product.group"
    _description = "HRX product group"

    name = fields.Char(string="Name", required=1)
    code = fields.Char(string="Code", required=1)
    description = fields.Text(string="Full Description")


class WkShippingPaymentMethod(models.Model):
    _name = "hrx.payment.method"
    _description = "HRX product method"

    name = fields.Char(string="Name", required=1)
    code = fields.Char(string="Code", required=1)
    description = fields.Text(string="Full Description")


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    make_hrx_hit = fields.Boolean(string="HRX Label Make")
    return_label_hrx = fields.Boolean(string="HRX Label Return")

    hrx_shipping_label = fields.Char(string="HRX Shipping Label", copy=False)
    multi_ship = fields.Boolean(string="Create Seperate Shipment for Every Package", default=True)

    def return_labeling_wepik(self):
        if self.carrier_id:
            self.carrier_id.hrx_send_shipping(self)

    def get_hrx_shipping_label(self, Label, Shipment):
        for record in self:
            attachments = []
            for item in range(len(Label)):
                attachments.append(('hrx_' + Shipment[item] + '.pdf', base64.b64decode(Label[item])))
                msg = "Label generated For HRX Shipment "

            if attachments:
                record.message_post(body=msg, subject="Label For HRX Shipment", attachments=attachments)
                return True


class ProductPackaging(models.Model):
    _inherit = 'stock.package.type'
    package_carrier_type = fields.Selection(
        selection_add=[('hrx', 'HRX')])
