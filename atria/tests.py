#!/usr/bin/python
#
# MIT License
#
# Copyright (c) 2020 William Oliveira de Lagos
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from django.test import TestCase, Client

# Create your tests here.

class RequestTestCase(TestCase):

    def setUp(self):
        self.cli = Client()
        
    def test_payments_endpoint(self):
        self.assertEqual(self.cli.get('v1/accounts/').status_code, 200)
        self.assertEqual(self.cli.get('v1/deliveries/').status_code, 200)
        self.assertEqual(self.cli.get('v1/contents/').status_code, 200)
        self.assertEqual(self.cli.get('v1/products/').status_code, 200)
        self.assertEqual(self.cli.get('v1/baskets/').status_code, 200)
        self.assertEqual(self.cli.get('v1/orders/').status_code, 200)
        self.assertEqual(self.cli.get('v1/blocks/').status_code, 200)

    def test_request_call(self):
        pass
        # self.assertEqual(self.cli.get('/pay/1').status_code, 404) # payment_redirect view
        # self.assertEqual(self.cli.get('/execute').status_code, 404) # payment_execute view
        # self.assertEqual(self.cli.get('/basketclean').status_code, 200) # basketclean view
        # self.assertEqual(self.cli.get('/basket').status_code, 200) # basket view
        # self.assertEqual(self.cli.get('/pagseguro/cart').status_code, 200) # pagsegurocart view
        # self.assertEqual(self.cli.get('/pagseguro').status_code, 200) # pagseguro view
        # self.assertEqual(self.cli.get('/paypal/cart').status_code, 200) # paypalcart view
        # self.assertEqual(self.cli.get('/paypal').status_code, 200) # paypal view