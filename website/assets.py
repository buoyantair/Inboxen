##
#    Copyright (C) 2015 Jessica Tallon & Matt Molyneaux
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

from django_assets import Bundle, register


css = Bundle(
    "css/bootstrap.css",
    "css/inboxen.css",
    filters="cssutils",
    output="compiled/css/website.%(version)s.css",
)


js = Bundle(
    "js/jquery.js",
    "js/bootstrap.js",
    filters="jsmin",
    output="compiled/js/website.%(version)s.js",
)

register("inboxen_css", css)
register("inboxen_js", js)