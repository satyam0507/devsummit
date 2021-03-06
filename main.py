#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import jinja2
import webapp2
import random
import re
import json
import mimetypes
import hashlib

# Grab the version from the package.json.
version = None
with open('./package.json') as f:
    data = json.load(f)
    version = data["version"]

# Set up the environment.
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def add_hash (path):
    blocksize = 32768
    file_hash = hashlib.sha256()
    file_path = re.sub(r'/devsummit/', './', path)

    with open(file_path) as file_to_hash:
        file_buffer = file_to_hash.read(blocksize)
        while (len(file_buffer) > 0):
            file_hash.update(file_buffer)
            file_buffer = file_to_hash.read(blocksize)

    return re.sub(r'(.*?)\.(.*)$', "\\1." + file_hash.hexdigest() + ".\\2", path)

JINJA_ENVIRONMENT.filters["add_hash"] = add_hash

class MainHandler(webapp2.RequestHandler):

    def get_template_info(self, url):
        t = {
            "path": url,
            "mimetype": (None, None),
            # Static files can be cached for a year, since there are hashes to
            # track changes to files, and so on. And we don't cache HTML.
            "cache": "public, max-age=31536000"
        }

        # If this is not a static file, use the base template.
        if re.search(r"^static/", url) is None:
            # Get the template based on the path the person is visiting.
            template = re.search(r"^([^/]+)/?", url)

            # For a total non-match we're looking at the root
            if template is None:
                t["path"] = "sections/home.html"
            else:
                t["path"] = "sections/" + template.group(1) + ".html"

            # HTML files should expire immediately.
            t["cache"] = "public, no-cache"

        # Strip off the hash from the path we're looking for.
        t["path"] = re.sub(r'[a-f0-9]{64}.', '', t["path"])

        # Make a special exception for the Service Worker, since we serve it
        # from /devsummit/sw.js, even though the file lives elsewhere.
        if re.search("sw.js$", url) is not None:
            t["path"] = "static/scripts/sw.js"

        t["mimetype"] = mimetypes.guess_type(t["path"])

        return t

    def get(self, url):
        is_partial = self.request.get('partial', None) is not None
        template_info = self.get_template_info(url)
        content_type = "text/plain"
        response = {
            "code": 404,
            "content": "URL not found: " + url
        }

        if template_info["mimetype"][0] is not None:
            content_type = template_info["mimetype"][0] + "; charset=utf-8"

        try:
            template = JINJA_ENVIRONMENT.get_template(template_info["path"])
            response["code"] = 200
            response["content"] = template.render(
                is_partial=is_partial,
                version=version
            )
        except jinja2.TemplateNotFound as template_name:
            print ("Template not found: " + template_name +
                " (requested by " + template_info["path"] + ")")

        # Make an ETag for the content
        etag = hashlib.sha256()
        etag.update(response["content"])

        self.response.status = response["code"]
        self.response.headers["Content-Type"] = content_type
        self.response.headers["ETag"] = etag.hexdigest()
        self.response.headers["Cache-Control"] = template_info["cache"]
        self.response.write(response["content"])

app = webapp2.WSGIApplication([
    ('/devsummit/?(.*)', MainHandler)
], debug=True)
