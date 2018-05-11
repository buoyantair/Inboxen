##
#    Copyright (C) 2014 Jessica Tallon & Matt Molyneaux
#
#    This file is part of Inboxen.
#
#    Inboxen is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Inboxen is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with Inboxen.  If not, see <http://www.gnu.org/licenses/>.
##

import datetime
import itertools

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
import mock

from inboxen import models
from inboxen.tests import factories
from inboxen.test import override_settings, InboxenTestCase


User = get_user_model()


class ModelTestCase(InboxenTestCase):
    """Test our custom methods"""
    def test_domain_queryset_methods(self):
        user = factories.UserFactory()
        other_user = factories.UserFactory(username="lalna")

        # all the permutations of Domains
        for args in itertools.product([True, False], [user, other_user, None]):
            factories.DomainFactory(enabled=args[0], owner=args[1])

        self.assertEqual(models.Domain.objects.available(user).count(), 2)
        self.assertEqual(models.Domain.objects.receiving().count(), 3)

    def test_inbox_create(self):
        user = factories.UserFactory()
        domain = factories.DomainFactory()

        with self.assertRaises(models.Domain.DoesNotExist):
            models.Inbox.objects.create()

        inbox = models.Inbox.objects.create(domain=domain, user=user)

        self.assertIsInstance(inbox.created, datetime.datetime)
        self.assertEqual(inbox.user, user)

    def test_inbox_create_reserved(self):
        user = factories.UserFactory()
        domain = factories.DomainFactory()

        def reserved_mock():
            # return True and then False, regardless of input
            ret_vals = [False, True]

            def inner(*args, **kwargs):
                return ret_vals.pop()

            return inner

        with mock.patch("inboxen.managers.is_reserved") as r_mock:
            r_mock.side_effect = reserved_mock()
            models.Inbox.objects.create(domain=domain, user=user)

            self.assertEqual(r_mock.call_count, 2)

    def test_inbox_create_integrity_error(self):
        user = factories.UserFactory()
        domain = factories.DomainFactory()
        inbox = models.Inbox.objects.create(domain=domain, user=user)

        def get_random_string_mock():
            # list of inboxes to be returned, in reverse order
            inboxes = ["a" * len(inbox.inbox), inbox.inbox]

            def inner(*args, **kwargs):
                return inboxes.pop()

            return inner

        with mock.patch("inboxen.managers.get_random_string") as r_mock:
            r_mock.side_effect = get_random_string_mock()
            new_inbox = models.Inbox.objects.create(domain=domain, user=user)

            self.assertEqual(new_inbox.inbox, "a" * len(inbox.inbox))
            self.assertEqual(r_mock.call_count, 2)

    def test_inbox_create_length(self):
        user = factories.UserFactory()
        domain = factories.DomainFactory()
        default_length = settings.INBOX_LENGTH

        with override_settings(INBOX_LENGTH=default_length + 1):
            inbox = models.Inbox.objects.create(user=user, domain=domain)
            self.assertEqual(len(inbox.inbox), default_length + 1)

            inbox = models.Inbox.objects.create(user=user, domain=domain, length=default_length + 3)
            self.assertEqual(len(inbox.inbox), default_length + 3)

        with self.assertRaises(AssertionError):
            inbox = models.Inbox.objects.create(user=user, domain=domain, length=-1)

    def test_inbox_from_string(self):
        user = factories.UserFactory()
        other_user = factories.UserFactory(username="lalna")

        inbox = factories.InboxFactory(user=user)
        email = "%s@%s" % (inbox.inbox, inbox.domain.domain)

        inbox2 = user.inbox_set.from_string(email=email)

        self.assertEqual(inbox, inbox2)

        with self.assertRaises(models.Inbox.DoesNotExist):
            other_user.inbox_set.from_string(email=email)

    def test_inbox_receiving(self):
        user = factories.UserFactory()

        # all the permutations of Inboxes that can receive
        params = (
            [True, False],
            [
                0,
                models.Inbox.flags.deleted,
                models.Inbox.flags.disabled,
                models.Inbox.flags.deleted | models.Inbox.flags.disabled,
                ~models.Inbox.flags.deleted & ~models.Inbox.flags.disabled,
            ],
            [user, None],
        )
        for args in itertools.product(*params):
            factories.InboxFactory(domain__enabled=args[0], flags=args[1], user=args[2])

        count = models.Inbox.objects.receiving().count()
        self.assertEqual(count, 2)

    def test_inbox_viewable(self):
        user = factories.UserFactory()
        other_user = factories.UserFactory(username="lalna")

        # all the permutations of Inboxes that can be viewed
        params = (
            [0, models.Inbox.flags.deleted, ~models.Inbox.flags.deleted],
            [user, other_user, None],
        )
        for args in itertools.product(*params):
            factories.InboxFactory(flags=args[0], user=args[1])

        count = models.Inbox.objects.viewable(user).count()
        self.assertEqual(count, 2)

    def test_email_viewable(self):
        user = factories.UserFactory()
        other_user = factories.UserFactory(username="lalna")

        # all the permutations of Emailss that can be viewed
        params = (
            [0, models.Inbox.flags.deleted, ~models.Inbox.flags.deleted],
            [user, other_user, None],
            [0, models.Email.flags.deleted, ~models.Email.flags.deleted],
        )
        for args in itertools.product(*params):
            factories.EmailFactory(inbox__flags=args[0], inbox__user=args[1], flags=args[2])

        count = models.Email.objects.viewable(user).count()
        self.assertEqual(count, 4)

    def test_add_last_activity(self):
        now = timezone.now()

        email = factories.EmailFactory(received_date=now)
        email.inbox.created = now - datetime.timedelta(2)
        email.inbox.save()

        inbox = factories.InboxFactory()
        inbox.created = now - datetime.timedelta(1)
        inbox.save()

        inboxes = list(models.Inbox.objects.all().add_last_activity())
        self.assertEqual(inboxes[0].last_activity, now)
        self.assertEqual(inboxes[1].last_activity, now - datetime.timedelta(1))

    def test_header_create(self):
        name = "X-Hello"
        data = "Hewwo"
        body = models.Body.objects.create(data=b"Hello", hashed="fakehash")
        part = models.PartList.objects.create(email=factories.EmailFactory(), body=body)

        header1 = part.header_set.create(name=name, data=data, ordinal=0)
        header2 = part.header_set.create(name=name, data=data, ordinal=1)

        self.assertEqual(header1[0].name_id, header2[0].name_id)
        self.assertEqual(header1[0].data_id, header2[0].data_id)
        self.assertEqual(header1[0].name.name, name)
        self.assertEqual(header1[0].data.data, data)
        self.assertTrue(header1[1])
        self.assertFalse(header2[1])

    def test_header_null_bytes(self):
        name = "X-Hello"
        data = "Hewwo \x00 test"
        body = models.Body.objects.create(data=b"Hello", hashed="fakehash")
        part = models.PartList.objects.create(email=factories.EmailFactory(), body=body)

        header, _ = part.header_set.create(name=name, data=data, ordinal=0)
        self.assertNotEqual(header.data.data, data)
        self.assertEqual(header.data.data, "Hewwo  test")

    def test_body_get_or_create(self):
        body_data = b"Hello"

        body1 = models.Body.objects.get_or_create(data=body_data)
        body2 = models.Body.objects.get_or_create(data=body_data)

        self.assertEqual(body1[0].id, body2[0].id)
        self.assertTrue(body1[1])
        self.assertFalse(body2[1])


class ModelFlagsTestCase(InboxenTestCase):
    def test_email_flags_order(self):
        # DON'T CHANGE ORDER OF THIS LIST
        flag_order = [
            "deleted",
            "read",
            "seen",
            "important",
            "view_all_headers",
        ]

        email_flags = list(models.Email.flags)

        self.assertEqual(flag_order, email_flags)

    def test_inbox_flags_order(self):
        # DON'T CHANGE ORDER OF THIS LIST
        flag_order = [
            "deleted",
            "new",
            "exclude_from_unified",
            "disabled",
            "pinned",
        ]

        inbox_flags = list(models.Inbox.flags)

        self.assertEqual(flag_order, inbox_flags)

    def test_profile_flags_order(self):
        # DON'T CHANGE ORDER OF THIS LIST
        flag_order = [
            "prefer_html_email",
            "unified_has_new_messages",
            "ask_images",
            "display_images",
        ]

        profile_flags = list(models.UserProfile.flags)

        self.assertEqual(flag_order, profile_flags)

    def test_liberation_flags_order(self):
        # DON'T CHANGE ORDER OF THIS LIST
        flag_order = [
            "running",
            "errored",
        ]

        liberation_flags = list(models.Liberation.flags)

        self.assertEqual(flag_order, liberation_flags)


class ModelReprTestCase(InboxenTestCase):
    """Repr is very useful when debugging via the shell"""

    def test_body(self):
        body = models.Body(hashed="1234")
        self.assertEqual(repr(body), "<Body: 1234>")

    def test_domain(self):
        domain = models.Domain(domain="example.com")
        self.assertEqual(repr(domain), "<Domain: example.com>")

    def test_email(self):
        email = models.Email(id=1234)
        self.assertEqual(repr(email), "<Email: 4d2>")

    def test_header(self):
        header = models.Header(name=models.HeaderName(name="example"))
        self.assertEqual(repr(header), "<Header: example>")

    def test_header_data(self):
        data = models.HeaderData(hashed="1234")
        self.assertEqual(repr(data), "<HeaderData: 1234>")

    def test_header_name(self):
        name = models.HeaderName(name="example")
        self.assertEqual(repr(name), "<HeaderName: example>")

    def test_inbox(self):
        inbox = models.Inbox(inbox="inbox", domain=models.Domain(domain="example.com"))
        self.assertEqual(repr(inbox), "<Inbox: inbox@example.com>")
        inbox.flags.deleted = True
        self.assertEqual(repr(inbox), "<Inbox: inbox@example.com (deleted)>")

    def test_liberation(self):
        liberation = models.Liberation(user=User(username="example"))
        self.assertEqual(repr(liberation), "<Liberation: Liberation for example>")

    def test_partlist(self):
        part = models.PartList(id="1234")
        self.assertEqual(repr(part), "<PartList: 1234>")

    def test_statistic(self):
        now = timezone.now()
        stat = models.Statistic(date=now)
        self.assertEqual(repr(stat), "<Statistic: %s>" % now)

    def test_inboxenprofile(self):
        profile = models.UserProfile(user=User(username="example"))
        self.assertEqual(repr(profile), "<UserProfile: Profile for example>")
