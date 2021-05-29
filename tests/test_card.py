"""
dj-stripe Card Model Tests.
"""
from copy import deepcopy
from unittest.mock import ANY, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from stripe.error import InvalidRequestError

from djstripe.exceptions import StripeObjectManipulationException
from djstripe.models import Card

from . import (
    FAKE_CARD,
    FAKE_CARD_III,
    FAKE_CARD_IV,
    FAKE_CUSTOM_ACCOUNT,
    FAKE_CUSTOMER,
    FAKE_STANDARD_ACCOUNT,
    AssertStripeFksMixin,
)


class CardTest(AssertStripeFksMixin, TestCase):
    def setUp(self):

        # create a Standard Stripe Account
        self.account = FAKE_STANDARD_ACCOUNT.create()

        user = get_user_model().objects.create_user(
            username="testuser", email="djstripe@example.com"
        )
        fake_empty_customer = deepcopy(FAKE_CUSTOMER)
        fake_empty_customer["default_source"] = None
        fake_empty_customer["sources"] = []

        self.customer = fake_empty_customer.create_for_user(user)

    def test_attach_objects_hook_without_customer(self):
        FAKE_CARD_DICT = deepcopy(FAKE_CARD)
        FAKE_CARD_DICT["customer"] = None

        card = Card.sync_from_stripe_data(FAKE_CARD_DICT)
        self.assertEqual(card.customer, None)

    def test_attach_objects_hook_without_account(self):
        card = Card.sync_from_stripe_data(FAKE_CARD)
        self.assertEqual(card.account, None)

    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    @patch(
        "stripe.Account.retrieve",
        return_value=deepcopy(FAKE_CUSTOM_ACCOUNT),
        autospec=True,
    )
    def test_api_retrieve_by_customer_equals_retrieval_by_account(
        self, account_retrieve_mock, customer_retrieve_mock
    ):
        # deepcopy the CardDict object
        FAKE_CARD_DICT = deepcopy(FAKE_CARD)

        card = Card.sync_from_stripe_data(deepcopy(FAKE_CARD_DICT))
        card_by_customer = card.api_retrieve()

        # Add account
        FAKE_CARD_DICT["account"] = self.account.id
        FAKE_CARD_DICT["customer"] = None

        card = Card.sync_from_stripe_data(FAKE_CARD_DICT)
        card_by_account = card.api_retrieve()

        # assert the same card object gets retrieved
        self.assertCountEqual(card_by_customer, card_by_account)

    def test_create_card_finds_customer_with_account_absent(self):
        card = Card.sync_from_stripe_data(FAKE_CARD)

        self.assertEqual(self.customer, card.customer)
        self.assertEqual(
            card.get_stripe_dashboard_url(), self.customer.get_stripe_dashboard_url()
        )

        self.assert_fks(
            card,
            expected_blank_fks={
                "djstripe.Card.account",
                "djstripe.BankAccount.account",
                "djstripe.Customer.coupon",
                "djstripe.Customer.default_payment_method",
                "djstripe.Customer.default_source",
            },
        )

    def test_create_card_finds_customer_with_account_present(self):
        # deepcopy the CardDict object
        FAKE_CARD_DICT = deepcopy(FAKE_CARD)
        # Add account
        FAKE_CARD_DICT["account"] = self.account.id

        card = Card.sync_from_stripe_data(FAKE_CARD_DICT)

        self.assertEqual(self.customer, card.customer)
        self.assertEqual(self.account, card.account)
        self.assertEqual(
            card.get_stripe_dashboard_url(),
            self.customer.get_stripe_dashboard_url(),
        )

        self.assert_fks(
            card,
            expected_blank_fks={
                "djstripe.BankAccount.account",
                "djstripe.Customer.coupon",
                "djstripe.Customer.default_payment_method",
                "djstripe.Customer.default_source",
            },
        )

    def test_create_card_finds_account_with_customer_absent(self):
        # deepcopy the CardDict object
        FAKE_CARD_DICT = deepcopy(FAKE_CARD)
        # Add account and remove customer
        FAKE_CARD_DICT["account"] = self.account.id
        FAKE_CARD_DICT["customer"] = None

        card = Card.sync_from_stripe_data(FAKE_CARD_DICT)

        self.assertEqual(self.account, card.account)
        self.assertEqual(
            card.get_stripe_dashboard_url(),
            self.account.get_stripe_dashboard_url(),
        )

        self.assert_fks(
            card,
            expected_blank_fks={
                "djstripe.Card.customer",
                "djstripe.BankAccount.account",
                "djstripe.Customer.coupon",
                "djstripe.Customer.default_payment_method",
                "djstripe.Customer.default_source",
            },
        )

    def test_str(self):
        card = Card.sync_from_stripe_data(FAKE_CARD)

        self.assertEqual(
            "<brand={brand}, last4={last4}, exp_month={exp_month}, "
            "exp_year={exp_year}, id={id}>".format(
                brand=FAKE_CARD["brand"],
                last4=FAKE_CARD["last4"],
                exp_month=FAKE_CARD["exp_month"],
                exp_year=FAKE_CARD["exp_year"],
                id=FAKE_CARD["id"],
            ),
            str(card),
        )

        self.assert_fks(
            card,
            expected_blank_fks={
                "djstripe.Card.account",
                "djstripe.Customer.coupon",
                "djstripe.Customer.default_payment_method",
                "djstripe.Customer.default_source",
            },
        )

    @patch("stripe.Token.create", autospec=True)
    def test_card_create_token(self, token_create_mock):
        card = {"number": "4242", "exp_month": 5, "exp_year": 2012, "cvc": 445}
        Card.create_token(**card)

        token_create_mock.assert_called_with(api_key=ANY, card=card)

    def test_api_call_no_customer_and_no_account(self):
        exception_message = (
            "Cards must be manipulated through either a Stripe Connected Account or a customer. "
            "Pass a Customer or an Account object into this call."
        )

        with self.assertRaisesMessage(
            StripeObjectManipulationException, exception_message
        ):
            Card._api_create()

        with self.assertRaisesMessage(
            StripeObjectManipulationException, exception_message
        ):
            Card.api_list()

    def test_api_call_bad_customer(self):
        exception_message = (
            "Cards must be manipulated through a Customer. "
            "Pass a Customer object into this call."
        )

        with self.assertRaisesMessage(
            StripeObjectManipulationException, exception_message
        ):
            Card._api_create(customer="fish")

        with self.assertRaisesMessage(
            StripeObjectManipulationException, exception_message
        ):
            Card.api_list(customer="fish")

    def test_api_call_bad_account(self):
        exception_message = (
            "Cards must be manipulated through a Stripe Connected Account. "
            "Pass an Account object into this call."
        )

        with self.assertRaisesMessage(
            StripeObjectManipulationException, exception_message
        ):
            Card._api_create(account="fish")

        with self.assertRaisesMessage(
            StripeObjectManipulationException, exception_message
        ):
            Card.api_list(account="fish")

    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    def test__api_create_with_account_absent(self, customer_retrieve_mock):
        stripe_card = Card._api_create(customer=self.customer, source=FAKE_CARD["id"])

        self.assertEqual(FAKE_CARD, stripe_card)

    @patch(
        "stripe.Account.retrieve",
        return_value=deepcopy(FAKE_CUSTOM_ACCOUNT),
        autospec=True,
    )
    def test__api_create_with_customer_absent(self, account_retrieve_mock):
        stripe_card = Card._api_create(account=self.account, source=FAKE_CARD_IV["id"])

        self.assertEqual(FAKE_CARD_IV, stripe_card)

    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    @patch(
        "stripe.Account.retrieve",
        return_value=deepcopy(FAKE_CUSTOM_ACCOUNT),
        autospec=True,
    )
    def test__api_create_with_customer_and_account(
        self, account_retrieve_mock, customer_retrieve_mock
    ):
        FAKE_CARD_DICT = deepcopy(FAKE_CARD)
        FAKE_CARD_DICT["account"] = self.account.id

        stripe_card = Card._api_create(
            account=self.account, customer=self.customer, source=FAKE_CARD_DICT["id"]
        )

        self.assertEqual(FAKE_CARD, stripe_card)

    @patch("tests.CardDict.delete", autospec=True)
    @patch("stripe.Card.retrieve", return_value=deepcopy(FAKE_CARD), autospec=True)
    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    def test_remove_card_by_customer(
        self, customer_retrieve_mock, card_retrieve_mock, card_delete_mock
    ):
        stripe_card = Card._api_create(customer=self.customer, source=FAKE_CARD["id"])
        Card.sync_from_stripe_data(stripe_card)

        self.assertEqual(1, self.customer.legacy_cards.count())

        card = self.customer.legacy_cards.all()[0]
        card.remove()

        self.assertEqual(0, self.customer.legacy_cards.count())
        self.assertTrue(card_delete_mock.called)

    @patch(
        "stripe.Account.retrieve",
        return_value=deepcopy(FAKE_CUSTOM_ACCOUNT),
        autospec=True,
    )
    def test_remove_card_by_account(self, account_retrieve_mock):

        stripe_card = Card._api_create(account=self.account, source=FAKE_CARD_IV["id"])
        Card.sync_from_stripe_data(stripe_card)
        # remove card
        count, _ = Card.objects.filter(id=stripe_card["id"]).delete()
        self.assertEqual(1, count)

    @patch(
        "stripe.Account.retrieve",
        return_value=deepcopy(FAKE_CUSTOM_ACCOUNT),
        autospec=True,
    )
    def test_remove_already_deleted_card_by_account(self, account_retrieve_mock):

        stripe_card = Card._api_create(account=self.account, source=FAKE_CARD_IV["id"])
        Card.sync_from_stripe_data(stripe_card)

        # remove card
        count, _ = Card.objects.filter(id=stripe_card["id"]).delete()
        self.assertEqual(1, count)

        # remove card again
        count, _ = Card.objects.filter(id=stripe_card["id"]).delete()
        self.assertEqual(0, count)

    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    def test_remove_already_deleted_card(self, customer_retrieve_mock):
        stripe_card = Card._api_create(customer=self.customer, source=FAKE_CARD["id"])
        Card.sync_from_stripe_data(stripe_card)

        self.assertEqual(self.customer.legacy_cards.count(), 1)
        card_object = self.customer.legacy_cards.first()
        Card.objects.filter(id=stripe_card["id"]).delete()
        self.assertEqual(self.customer.legacy_cards.count(), 0)
        card_object.remove()
        self.assertEqual(self.customer.legacy_cards.count(), 0)

    @patch("djstripe.models.Card._api_delete", autospec=True)
    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    def test_remove_no_such_source(self, customer_retrieve_mock, card_delete_mock):
        stripe_card = Card._api_create(customer=self.customer, source=FAKE_CARD["id"])
        Card.sync_from_stripe_data(stripe_card)

        card_delete_mock.side_effect = InvalidRequestError("No such source:", "blah")

        self.assertEqual(1, self.customer.legacy_cards.count())

        card = self.customer.legacy_cards.all()[0]
        card.remove()

        self.assertEqual(0, self.customer.legacy_cards.count())
        self.assertTrue(card_delete_mock.called)

    @patch("djstripe.models.Card._api_delete", autospec=True)
    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    def test_remove_no_such_customer(self, customer_retrieve_mock, card_delete_mock):
        stripe_card = Card._api_create(customer=self.customer, source=FAKE_CARD["id"])
        Card.sync_from_stripe_data(stripe_card)

        card_delete_mock.side_effect = InvalidRequestError("No such customer:", "blah")

        self.assertEqual(1, self.customer.legacy_cards.count())

        card = self.customer.legacy_cards.all()[0]
        card.remove()

        self.assertEqual(0, self.customer.legacy_cards.count())
        self.assertTrue(card_delete_mock.called)

    @patch("djstripe.models.Card._api_delete", autospec=True)
    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    def test_remove_unexpected_exception(
        self, customer_retrieve_mock, card_delete_mock
    ):
        stripe_card = Card._api_create(customer=self.customer, source=FAKE_CARD["id"])
        Card.sync_from_stripe_data(stripe_card)

        card_delete_mock.side_effect = InvalidRequestError(
            "Unexpected Exception", "blah"
        )

        self.assertEqual(1, self.customer.legacy_cards.count())

        card = self.customer.legacy_cards.all()[0]

        with self.assertRaisesMessage(InvalidRequestError, "Unexpected Exception"):
            card.remove()

    @patch(
        "stripe.Customer.retrieve", return_value=deepcopy(FAKE_CUSTOMER), autospec=True
    )
    def test_api_list(self, customer_retrieve_mock):
        card_list = Card.api_list(customer=self.customer)

        self.assertCountEqual([FAKE_CARD, FAKE_CARD_III], [i for i in card_list])
