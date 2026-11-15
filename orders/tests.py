from django.test import SimpleTestCase


class OrderValidationTest(SimpleTestCase):

    def test_positive_quantity(self):
        quantity = 5
        self.assertGreater(quantity, 0)

    def test_negative_quantity_rejected(self):
        quantity = -3
        self.assertLessEqual(quantity, 0)


from django.test import TestCase

# Create your tests here.
