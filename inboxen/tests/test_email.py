# -*- coding: utf-8 -*-
##
#    Copyright (C) 2014-2015 Jessica Tallon & Matt Molyneaux
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
from __future__ import unicode_literals

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core import urlresolvers
from salmon import mail
import six

import mock

from inboxen import models
from inboxen.tests import factories
from inboxen.tests.example_emails import (
    BADLY_ENCODED_BODY,
    BAD_HTTP_EQUIV_BODY,
    BODILESS_BODY,
    BODY,
    CHARSETLESS_BODY,
    EMPTY_ANCHOR_TAG,
    EXAMPLE_ALT,
    EXAMPLE_DIGEST,
    EXAMPLE_PREMAILER_BROKEN_CSS,
    EXAMPLE_PREMIME_EMAIL,
    EXAMPLE_SIGNED_FORWARDED_DIGEST,
    LONELY_ANCHOR_TAG,
    METALESS_BODY,
    UNSUPPORTED_CSS_BODY,
)
from inboxen.test import InboxenTestCase, MockRequest
from inboxen.utils import email as email_utils
from router.app.helpers import make_email


class EmailViewTestCase(InboxenTestCase):
    def setUp(self):
        super(EmailViewTestCase, self).setUp()

        self.user = factories.UserFactory()
        self.email = factories.EmailFactory(inbox__user=self.user)
        body = factories.BodyFactory(data=BODY)
        part = factories.PartListFactory(email=self.email, body=body)
        factories.HeaderFactory(part=part, name="From")
        factories.HeaderFactory(part=part, name="Subject")
        factories.HeaderFactory(part=part, name="Content-Type", data="text/html; charset=\"utf-8\"")

        login = self.client.login(username=self.user.username, password="123456", request=MockRequest(self.user))

        if not login:
            raise Exception("Could not log in")

    def get_url(self):
        kwargs = {
            "inbox": self.email.inbox.inbox,
            "domain": self.email.inbox.domain.domain,
            "id": self.email.eid,
        }
        return urlresolvers.reverse("email-view", kwargs=kwargs)

    def test_get(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

        # check that delete button has correct value
        button = "value=\"%s\" name=\"delete-single\""
        button = button % self.email.eid
        self.assertIn(button, response.content.decode("utf-8"))

        # check that premailer removes invalid CSS
        self.assertNotIn("awesomebar-sprite.png", response.content.decode("utf-8"))

        # check for same-origin
        self.assertIn('<meta name="referrer" content="same-origin">', response.content.decode("utf-8"))

    def test_get_with_headers(self):
        response = self.client.get(self.get_url() + "?all-headers=1")
        self.assertEqual(response.status_code, 200)

        headersfetchall = response.context["headersfetchall"]
        self.assertTrue(headersfetchall)

        response = self.client.get(self.get_url() + "?all-headers=0")
        self.assertEqual(response.status_code, 200)

        headersfetchall = response.context["headersfetchall"]
        self.assertFalse(headersfetchall)

    def test_body_encoding_with_imgDisplay(self):
        self.user.inboxenprofile.display_images = models.UserProfile.ASK
        self.user.inboxenprofile.save()

        response = self.client.get(self.get_url() + "?imgDisplay=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        self.assertFalse(response.context["email"]["ask_images"] and response.context["email"]["has_images"])

        body = response.context["email"]["bodies"][0]
        self.assertIn(u"<p style=\"color:#fff\">&#160;</p>", body)
        self.assertIn(u"<p style=\"color:#fff\">&#163;&#163;&#163;</p>", body)
        self.assertIn(u"http://example.com/coolface.jpg", body)
        self.assertIn(u"img width=\"10\" height=\"10\"", body)
        self.assertNotIn(staticfiles_storage.url("imgs/placeholder.svg"), body)

        # premailer should have worked fine
        self.assertNotIn("Part of this message could not be parsed - it may not display correctly",
                         response.content.decode("utf-8"))

        # csp
        self.assertIn("style-src 'self' 'unsafe-inline';", response["content-security-policy"])
        self.assertIn("img-src 'self' https:;", response["content-security-policy"])

    def test_body_encoding_without_imgDisplay(self):
        self.user.inboxenprofile.display_images = models.UserProfile.ASK
        self.user.inboxenprofile.save()

        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        self.assertTrue(response.context["email"]["ask_images"] and response.context["email"]["has_images"])

        body = response.context["email"]["bodies"][0]
        self.assertIn(u"<p style=\"color:#fff\">&#160;</p>", body)
        self.assertIn(u"<p style=\"color:#fff\">&#163;&#163;&#163;</p>", body)
        self.assertNotIn(u"http://example.com/coolface.jpg", body)
        self.assertIn(u"img width=\"10\" height=\"10\"", body)
        self.assertIn(staticfiles_storage.url("imgs/placeholder.svg"), body)

        # premailer should have worked fine
        self.assertNotIn("Part of this message could not be parsed - it may not display correctly",
                         response.content.decode("utf-8"))

        # csp
        self.assertIn("style-src 'self' 'unsafe-inline';", response["content-security-policy"])
        self.assertIn("img-src 'self';", response["content-security-policy"])
        self.assertNotIn("img-src 'self' https:;", response["content-security-policy"])

    def test_body_no_ask_images(self):
        self.user.inboxenprofile.display_images = models.UserProfile.NO_DISPLAY
        self.user.inboxenprofile.save()

        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        self.assertFalse(response.context["email"]["ask_images"] and response.context["email"]["has_images"])

        body = response.context["email"]["bodies"][0]
        self.assertIn(u"<p style=\"color:#fff\">&#160;</p>", body)
        self.assertIn(u"<p style=\"color:#fff\">&#163;&#163;&#163;</p>", body)
        self.assertNotIn(u"http://example.com/coolface.jpg", body)
        self.assertIn(u"img width=\"10\" height=\"10\"", body)
        self.assertIn(staticfiles_storage.url("imgs/placeholder.svg"), body)

        # premailer should have worked fine
        self.assertNotIn("Part of this message could not be parsed - it may not display correctly",
                         response.content.decode("utf-8"))

        # csp
        self.assertIn("style-src 'self' 'unsafe-inline';", response["content-security-policy"])
        self.assertIn("img-src 'self';", response["content-security-policy"])
        self.assertNotIn("img-src 'self' https:;", response["content-security-policy"])

    def test_attachments_get(self):
        part = self.email.parts.get()
        url = urlresolvers.reverse("email-attachment", kwargs={"attachmentid": part.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        part_id = part.id + 1000
        url = urlresolvers.reverse("email-attachment", kwargs={"attachmentid": part_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_post(self):
        important = self.email.important

        params = {"important-toggle": ""}
        response = self.client.post(self.get_url(), params)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.get_url())
        email = models.Email.objects.get(pk=self.email.pk)
        self.assertNotEqual(email.important, important)

        important = not important
        response = self.client.post(self.get_url(), params)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.get_url())
        email = models.Email.objects.get(pk=self.email.pk)
        self.assertNotEqual(email.important, important)

    def test_html_a(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        body = response.context["email"]["bodies"][0]
        expected_string = u'<a href="/click/?url=http%3A//example.com/%3Fq%3Dthing" target="_blank" rel="noreferrer">link</a>'  # noqa: E501
        self.assertIn(expected_string, body)

    def test_not_allowed_tag(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        body = response.context["email"]["bodies"][0]
        self.assertNotIn(u"script", body)
        self.assertNotIn(u"I'm a bad email", body)

    def test_not_allowed_attr(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        body = response.context["email"]["bodies"][0]
        self.assertNotIn(u"onClick=\"alert('Idiot!')\"", body)
        self.assertIn(u"<p style=\"color:#fff\">Click me!</p>", body)
        self.assertNotIn(u"<p id=\"email-17\">", body)

    # TODO: test body choosing with multipart emails


class BadEmailTestCase(InboxenTestCase):
    def setUp(self):
        super(BadEmailTestCase, self).setUp()

        self.user = factories.UserFactory()
        self.email = factories.EmailFactory(inbox__user=self.user)
        body = factories.BodyFactory(data=BODY)
        part = factories.PartListFactory(email=self.email, body=body)
        factories.HeaderFactory(part=part, name="From")
        factories.HeaderFactory(part=part, name="Subject")
        factories.HeaderFactory(part=part, name="Content-Type", data="text/html; charset=\"windows-1252\"")
        factories.HeaderFactory(part=part, name="Content-Disposition", data="inline; filename=\"He\n\rl\rlo\nß.jpg\"")

        self.email_metaless = factories.EmailFactory(inbox__user=self.user)
        body = factories.BodyFactory(data=METALESS_BODY)
        part = factories.PartListFactory(email=self.email_metaless, body=body)
        factories.HeaderFactory(part=part, name="From")
        factories.HeaderFactory(part=part, name="Subject")
        factories.HeaderFactory(part=part, name="Content-Type", data="text/html; charset=\"ascii\"")

        login = self.client.login(username=self.user.username, password="123456", request=MockRequest(self.user))

        if not login:
            raise Exception("Could not log in")

    def get_url(self, email=None):
        if email is None:
            email = self.email

        kwargs = {
            "inbox": email.inbox.inbox,
            "domain": email.inbox.domain.domain,
            "id": email.eid,
        }
        return urlresolvers.reverse("email-view", kwargs=kwargs)

    def test_body_encoding_with_imgDisplay(self):
        response = self.client.get(self.get_url() + "?imgDisplay=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        body = response.context["email"]["bodies"][0]
        self.assertIn(u"<p style=\"color:#fff\">&#160;</p>", body)
        self.assertIn(u"<p style=\"color:#fff\">&#163;&#163;&#163;</p>", body)
        self.assertIn(u"http://example.com/coolface.jpg", body)
        self.assertIn(u"img width=\"10\" height=\"10\"", body)

        # premailer should have worked fine
        self.assertNotIn("Part of this message could not be parsed - it may not display correctly",
                         response.content.decode("utf-8"))

    def test_body_encoding_without_imgDisplay(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        body = response.context["email"]["bodies"][0]
        self.assertIn(u"<p style=\"color:#fff\">&#160;</p>", body)
        self.assertIn(u"<p style=\"color:#fff\">&#163;&#163;&#163;</p>", body)
        self.assertNotIn(u"http://example.com/coolface.jpg", body)
        self.assertIn(u"img width=\"10\" height=\"10\"", body)

        # premailer should have worked fine
        self.assertNotIn("Part of this message could not be parsed - it may not display correctly",
                         response.content.decode("utf-8"))

    def test_body_with_no_meta(self):
        response = self.client.get(self.get_url(self.email_metaless) + "?imgDisplay=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        body = response.context["email"]["bodies"][0]
        self.assertIn(u"<p style=\"color:#fff\">&#160;</p>", body)
        self.assertIn(u"<p style=\"color:#fff\">$$$</p>", body)
        self.assertIn(u"http://example.com/coolface.jpg", body)
        self.assertIn(u"img width=\"10\" height=\"10\"", body)

        # premailer should have worked fine
        self.assertNotIn("Part of this message could not be parsed - it may not display correctly",
                         response.content.decode("utf-8"))

    def test_attachments_get(self):
        part = self.email.parts.get()
        url = urlresolvers.reverse("email-attachment", kwargs={"attachmentid": part.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        if six.PY3:
            self.assertIn("He l lo ß.jpg", response["Content-Disposition"])
        else:
            self.assertIn("He l lo ß.jpg".encode("utf-8"), response["Content-Disposition"])

    def test_html_a(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        body = response.context["email"]["bodies"][0]
        expected_string = '<a href="/click/?url=http%3A//example.com/%3Fq%3Dthing" target="_blank" rel="noreferrer">link</a>'  # noqa: E501
        self.assertIn(expected_string, body)


class RealExamplesTestCase(InboxenTestCase):
    def setUp(self):
        self.user = factories.UserFactory()
        self.inbox = factories.InboxFactory(user=self.user)

        login = self.client.login(username=self.user.username, password="123456", request=MockRequest(self.user))

        if not login:
            raise Exception("Could not log in")

    def get_url(self):
        kwargs = {
            "inbox": self.email.inbox.inbox,
            "domain": self.email.inbox.domain.domain,
            "id": self.email.eid,
        }
        return urlresolvers.reverse("email-view", kwargs=kwargs)

    def test_digest(self):
        self.msg = mail.MailRequest("", "", "", EXAMPLE_DIGEST)
        make_email(self.msg, self.inbox)
        self.email = models.Email.objects.get()

        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

        # this email should display all leaves
        leaf_part_count = len([i for i in self.email.parts.all() if i.is_leaf_node()
                               and i.content_type != "application/pgp-signature"])
        self.assertEqual(len(response.context["email"]["bodies"]), leaf_part_count)

    def test_signed_forwarded_digest(self):
        self.msg = mail.MailRequest("", "", "", EXAMPLE_SIGNED_FORWARDED_DIGEST)
        make_email(self.msg, self.inbox)
        self.email = models.Email.objects.get()

        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

        leaf_part_count = len([i for i in self.email.parts.all() if i.is_leaf_node()])
        self.assertEqual(leaf_part_count, 12)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        self.assertEqual(response.context["email"]["bodies"][0], "<pre>Hello\n</pre>")

    def test_alterative(self):
        self.msg = mail.MailRequest("", "", "", EXAMPLE_ALT)
        make_email(self.msg, self.inbox)
        self.email = models.Email.objects.get()

        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)

    def test_bad_css(self):
        """This test uses an example email that causes issue #47"""
        self.msg = mail.MailRequest("", "", "", EXAMPLE_PREMAILER_BROKEN_CSS)
        make_email(self.msg, self.inbox)
        self.email = models.Email.objects.get()

        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        self.assertNotIn("Part of this message could not be parsed - it may not display correctly",
                         response.content.decode("utf-8"))

    def test_premime(self):
        self.msg = mail.MailRequest("", "", "", EXAMPLE_PREMIME_EMAIL)
        make_email(self.msg, self.inbox)
        self.email = models.Email.objects.get()

        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.email.parts.all().count(), 1)
        self.assertEqual(len(response.context["email"]["bodies"]), 1)
        self.assertEqual(response.context["email"]["bodies"][0], "<pre>Hi,\n\nHow are you?\n\nThanks,\nTest\n</pre>")


class AttachmentTestCase(InboxenTestCase):
    def setUp(self):
        super(AttachmentTestCase, self).setUp()

        self.user = factories.UserFactory()
        self.email = factories.EmailFactory(inbox__user=self.user)
        body = factories.BodyFactory(data=BODY)
        self.part = factories.PartListFactory(email=self.email, body=body)
        self.content_type_header, _ = factories.HeaderFactory(part=self.part, name="Content-Type",
                                                              data="text/html; charset=\"utf-8\"")

        login = self.client.login(username=self.user.username, password="123456", request=MockRequest(self.user))

        if not login:
            raise Exception("Could not log in")

    def test_no_name(self):
        url = urlresolvers.reverse("email-attachment", kwargs={"attachmentid": self.part.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], "attachment")

    def test_name_in_cc(self):
        header_data = self.content_type_header.data
        header_data.data = "text/html; charset=\"utf-8\"; name=\"Växjö.jpg\""
        header_data.save()

        url = urlresolvers.reverse("email-attachment", kwargs={"attachmentid": self.part.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        if six.PY3:
            self.assertEqual(response["Content-Disposition"], "attachment; filename=\"Växjö.jpg\"")
        else:
            self.assertEqual(response["Content-Disposition"], "attachment; filename=\"Växjö.jpg\"".encode("utf-8"))

    def test_name_in_cd(self):
        factories.HeaderFactory(part=self.part, name="Content-Disposition", data="inline; filename=\"Växjö.jpg\"")
        url = urlresolvers.reverse("email-attachment", kwargs={"attachmentid": self.part.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        if six.PY3:
            self.assertEqual(response["Content-Disposition"], "attachment; filename=\"Växjö.jpg\"")
        else:
            self.assertEqual(response["Content-Disposition"], "attachment; filename=\"Växjö.jpg\"".encode("utf-8"))


class UtilityTestCase(InboxenTestCase):
    def test_is_unicode(self):
        string = "Hey there!"
        self.assertTrue(isinstance(email_utils.unicode_damnit(string), six.text_type))

    def test_unicode_passthrough(self):
        already_unicode = u"€"

        # if this doesn't passthrough, it will error
        email_utils.unicode_damnit(already_unicode, "ascii", "strict")

    def test_clean_html_no_body(self):
        email = {"display_images": True}
        with mock.patch("inboxen.utils.email.messages.info", side_effect=self.failureException("Unexpected message")):
            returned_body = email_utils._clean_html_body(None, email, BODILESS_BODY, "utf-8")

            self.assertIn('<a href="/click/?url=http%3A//tinyletter.com/asym/confirm%3Fid%3Duuid"', returned_body)

    def test_clean_html_no_charset(self):
        email = {"display_images": True}
        returned_body = email_utils._clean_html_body(None, email, CHARSETLESS_BODY, "ascii")
        self.assertIsInstance(returned_body, six.text_type)

    def test_clean_html_unsupported_css(self):
        email = {"display_images": True, "eid": "abc"}
        with mock.patch("inboxen.utils.email.messages") as msg_mock:
            returned_body = email_utils._clean_html_body(None, email, UNSUPPORTED_CSS_BODY, "ascii")
            self.assertEqual(msg_mock.info.call_count, 1)
        self.assertIsInstance(returned_body, six.text_type)

    def test_clean_html_balance_tags_when_closing_tag_missing(self):
        email = {"display_images": True, "eid": "abc"}
        expected_html = """<a href="/click/?url=https%3A//example.com" target="_blank" rel="noreferrer"></a>"""

        # unbalanced tags should be given a closing tag
        returned_body = email_utils._clean_html_body(None, email, LONELY_ANCHOR_TAG, "ascii")
        self.assertEqual(returned_body, expected_html)

    def test_clean_html_no_strip_closing_tags_when_empty(self):
        email = {"display_images": True, "eid": "abc"}
        expected_html = """<a href="/click/?url=https%3A//example.com" target="_blank" rel="noreferrer"></a>"""

        # empty tags should not have their closing tag removed
        returned_body = email_utils._clean_html_body(None, email, EMPTY_ANCHOR_TAG, "ascii")
        self.assertEqual(returned_body, expected_html)

    def test_render_body_bad_encoding(self):
        email = {"display_images": True, "eid": "abc"}
        part = mock.Mock()
        part.content_type = "text/html"
        part.charset = "utf-8"
        part.body.data = BADLY_ENCODED_BODY

        with mock.patch("inboxen.utils.email.messages") as msg_mock:
            returned_body = email_utils.render_body(None, email, [part])
            self.assertEqual(msg_mock.error.call_count, 1)
        self.assertIsInstance(returned_body, six.text_type)

    def test_render_body_bad_http_equiv(self):
        email = {"display_images": True, "eid": "abc"}
        part = mock.Mock()
        part.content_type = "text/html"
        part.charset = "utf-8"
        part.body.data = BAD_HTTP_EQUIV_BODY

        returned_body = email_utils.render_body(None, email, [part])
        self.assertIsInstance(returned_body, six.text_type)

    def test_invalid_charset(self):
        text = "Växjö".encode("utf-8")
        self.assertEqual(email_utils.unicode_damnit(text, "utf-8"), u"Växjö")
        self.assertEqual(email_utils.unicode_damnit(text, "six.text_type"), u"V\ufffd\ufffdxj\ufffd\ufffd")

    def test_find_bodies_with_bad_mime_tree(self):
        email = factories.EmailFactory()
        body = factories.BodyFactory(data=b"This mail body is searchable")  # build 1 body and use that

        # the root part, multipart/alternative
        root_part = factories.PartListFactory(email=email, body=body)
        factories.HeaderFactory(part=root_part, name="Content-Type", data="multipart/alternative")

        # first text part
        alt1_part = factories.PartListFactory(email=email, body=body, parent=root_part)
        factories.HeaderFactory(part=alt1_part, name="Content-Type", data="text/plain; charset=\"ascii\"")

        # second text part
        alt2_part = factories.PartListFactory(email=email, body=body, parent=root_part)
        factories.HeaderFactory(part=alt2_part, name="Content-Type", data="text/plain; charset=\"ascii\"")

        # make first text part invalid by giving it a child
        alt1_child_part = factories.PartListFactory(email=email, body=body, parent=alt1_part)
        factories.HeaderFactory(part=alt1_child_part, name="Content-Type", data="text/plain; charset=\"ascii\"")

        # find_bodies returns a list of lists, so flatten it out
        bodies = [part for part_list in email_utils.find_bodies(email.get_parts()) for part in part_list]
        # we should only see one part
        self.assertEqual(len(bodies), 1)
        # and it should be a leaf node
        self.assertTrue(bodies[0].is_leaf_node())
        self.assertEqual(bodies[0], alt2_part)
