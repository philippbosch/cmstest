# -*- coding: utf-8 -*-
import os.path

from django.conf.urls.defaults import *
from django.contrib import admin
from django.conf import settings
admin.autodiscover()

urlpatterns = patterns('',
    (r'^media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': os.path.join(settings.PROJECT_ROOT, 'media')}),
    (r'^admin/', include(admin.site.urls)),
    (r'^tinymce/', include('tinymce.urls')),
    url(r'^jssettings/$', 'django.views.generic.simple.direct_to_template', {'template': 'jssettings.js', 'mimetype': 'application/x-javascript', 'extra_context': {'settings':settings}}, name="jssettings"),
    (r'^', include('cms.urls')),
)


# monkey-patching django-cms' TextPlugin to not show a preview in the admin …
from cms.plugins.text.cms_plugins import TextPlugin
TextPlugin.admin_preview = False

# … and to expand the tinyMCE widget to the correct height.
from cms.plugins.text.widgets.tinymce_widget import TinyMCEEditor

render_orig = TinyMCEEditor.render
def tinymceeditor_render(self, name, value, attrs=None):
    if not attrs:
        attrs = {}
    attrs['rows'] = 22
    return render_orig(self, name, value, attrs)

TinyMCEEditor.render = tinymceeditor_render



# monkey-patching django-cms' FilePlugin to ignore case when looking for icons
from cms.plugins.file.models import File
get_ext_orig = File.get_ext
def File_get_ext(self):
    return get_ext_orig(self).lower()

File.get_ext = File_get_ext
