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

from django import test
from django.core import urlresolvers
from django.conf import settings as dj_settings

from inboxen import models

class HomeViewTestCase(test.TestCase):
    fixtures = ['inboxen_testdata.json']

    def setUp(self):
        super(HomeViewTestCase, self).setUp()
        self.user = models.User.objects.get(id=1)

        login = self.client.login(username=self.user.username, password="123456")

        if not login:
            raise Exception("Could not log in")

    def get_url(self):
        return urlresolvers.reverse("user-home")

    def test_context(self):
        response = self.client.get(self.get_url())
        context_settings = response.context['settings']

        # test that something is getting set
        self.assertEqual(dj_settings.SITE_NAME, context_settings["SITE_NAME"])

        # Please add any settings that may contain passwords or secrets:
        self.assertEqual("SECRET_KEY" in context_settings, False)
        self.assertEqual("DATABASES" in context_settings, False)

    def test_get(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_pagin(self):
        # there should be 150 inboxes in the test fixtures
        # and pages are paginated by 100 items
        response = self.client.get(self.get_url() + "2")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(self.get_url() + "3")
        self.assertEqual(response.status_code, 404)
