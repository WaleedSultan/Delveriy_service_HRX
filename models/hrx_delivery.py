
from odoo import  fields, models, _
import requests
import json
import logging
from odoo.exceptions import ValidationError, UserError
import re
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)
try:
    from suds.client import Client
except:
    raise Warning("Please install suds: pip3 install suds-py3")

shipping_service_live = 'https://wop.hrx.eu/api/v1/orders'



class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"
    hrx_client_id = fields.Char(string="Picking ID")
    hrx_client_name = fields.Char(string="Picking Name")
    hrx_client_country = fields.Char(string="Picking Country")
    hrx_client_city = fields.Char(string="Picking City")
    hrx_client_zip = fields.Char(string="Picking Zip")
    hrx_client_address = fields.Char(string="Picking Address")
    hrx_id = fields.Char(string="API ID")
    hrx_picking_id = fields.Integer(string="id")
    def get_client_credentials(self):
        headers = {
                'Authorization': 'Bearer %s'%self.hrx_id
            }
        company_cred_url = "https://wop.hrx.eu/api/v1/pickup_locations"
        company_cred_request = requests.request('GET', company_cred_url, headers=headers)
        string_data = company_cred_request.content.decode('utf-8')
        credentials = json.loads(string_data)[0]
        self.hrx_client_id = credentials['id']
        self.hrx_client_address = credentials['address']
        self.hrx_client_city = credentials['city']
        self.hrx_client_country = credentials['country']
        self.hrx_client_zip = credentials['zip']
        self.hrx_client_name = credentials['name']






    def hrx_send_shipping(self, pickings, shipping_status=True):  # OWN
        self.hrx_picking_id = str(pickings.id)
        for obj in self:
            packaging_ids = pickings.move_line_ids_without_package
            order = pickings.sale_id if pickings.sale_id else None
            tracking_number = pickings.carrier_tracking_ref
            # try:
            if not tracking_number or not shipping_status:
                response_list = self.create_hrx_shipment_order(order, pickings=pickings, packaging_ids=packaging_ids,
                                                      shipping_status=shipping_status)
                if response_list['id']:
                    pickings.message_post(body="Shipment created successfully")
                else:
                    pickings.message_post(body="Shipment unsuccessfully")
            result = [{
                'exact_price': pickings.sale_id.amount_total if pickings.sale_id else 0.00,
                'tracking_number': 'Waiting State'
            }]
            return result
    def create_hrx_shipment_order(self, order, pickings, packaging_ids, shipping_status):
        headers = {
            'Authorization': 'Bearer %s' % self.hrx_id
        }

        dimentions = self.env['choose.delivery.package'].search([('picking_id', '=', pickings.id)])



        payload = {
            "sender_reference": order.id,
            "sender_comment": "Deliver with care",
            "pickup_location_id": pickings.carrier_id.hrx_client_id,
            "pickup_location_country": pickings.carrier_id.hrx_client_country,
            "pickup_location_city": pickings.carrier_id.hrx_client_city,
            "pickup_location_zip": pickings.carrier_id.hrx_client_zip,
            "pickup_location_address": pickings.carrier_id.hrx_client_address,
            "pickup_location_name": pickings.carrier_id.hrx_client_name,
            "pickup_location_phone": "+37120637717",
            "delivery_kind": "courier",
            "delivery_location_country": order.partner_id.country_code,
            "delivery_location_city": order.partner_id.city,
            "delivery_location_zip": order.partner_id.zip,
            "delivery_location_address": order.partner_id.street,
            "length_cm": dimentions.length_hrx,
            "width_cm": dimentions.width_hrx,
            "height_cm": dimentions.height_hrx,
            "weight_kg": dimentions.shipping_weight,
            "recipient_name": order.partner_id.name,
            "recipient_email": order.partner_id.email,
            "recipient_phone": self.remove_country_code(order.partner_id.phone)
        }

        response = requests.request('POST', shipping_service_live, data=payload, headers=headers)
        if response.status_code not in [201,200]:
            raise UserError(response.json()['error'])

        json_response = response.json()
        stock_picking_obj = self.env['stock.picking'].search([('id', '=', self.hrx_picking_id)])
        stock_picking_obj.hrx_id = json_response['id']

        return json_response

    def remove_country_code(self, phone_number):
        phone_number = re.sub(r'^\+\d+', '', phone_number)
        phone_number = re.sub(r'\s+', '', phone_number)
        return phone_number

    def hrx_get_return_label(self):
        print('return label hrx')
        pass


    def hrx_cancel_shipment(self, pickings):
        raise ValidationError('This feature is not supported by HRX.....')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    hrx_id = fields.Char(string="HRX ID", readonly=True)


    def print_hrx_label(self):
        headers = {
            'Authorization': 'Bearer %s' %self.carrier_id.hrx_id
        }
        id = str(self.hrx_id)
        label_url = "https://wop.hrx.eu/api/v1/orders/%s/label" % id
        label_request = requests.request('GET', label_url, headers=headers)
        # time.sleep(1)
        if label_request.status_code not in [200,201]:
            raise UserError('Please wait 30 secoonds')


        string_data = label_request.content.decode('utf-8')
        dictionary = json.loads(string_data)
        pdf = self.env['ir.attachment'].create(
            {
                'name': ('Label-%s.pdf' % (str(dictionary['tracking_number']))),
                'type': 'binary',
                'datas': dictionary['file_content'],
                'res_model': 'delivery.carrier',
                'res_id': self.id
            })

        logmessage = (
                _("Label created into HRX <br/> <b>Tracking Number : </b>%s") % (
            str(dictionary['tracking_number'])))

        self.message_post(body=logmessage, attachment_ids=[pdf.id])

        self.carrier_tracking_ref = dictionary['tracking_number']

    def return_hrx_label(self):
        headers = {
            'Authorization': 'Bearer %s' %self.carrier_id.hrx_id
        }
        label_url = "https://wop.hrx.eu/api/v1/orders/%s" % self.hrx_id
        label_request1 = requests.request('GET', label_url, headers=headers)
        string_data1 = label_request1.content.decode('utf-8')
        dictionary1 = json.loads(string_data1)
        if dictionary1['can_print_return_label']:
            label_url = "https://wop.hrx.eu/api/v1/orders/%s/return_label" % self.hrx_id
            label_request = requests.request('GET', label_url, headers=headers)
            string_data = label_request.content.decode('utf-8')
            dictionary = json.loads(string_data)

            pdf = self.env['ir.attachment'].create(
                {
                    'name': ('Return_Label-%s.pdf' % (str(dictionary['tracking_number']))),
                    'type': 'binary',
                    'datas': dictionary['file_content'],
                    'res_model': 'delivery.carrier',
                    'res_id': self.id
                })

            logmessage = (
                    _("Return Label created into HRX <br/> <b>Tracking Number : </b>%s") % (
                str(dictionary['tracking_number'])))

            self.message_post(body=logmessage, attachment_ids=[pdf.id])
        else:
            self.message_post(body='You cannot print Return Label')








