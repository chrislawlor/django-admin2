from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.encoding import force_text
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext as _

from . import utils


def get_description(action):
    if hasattr(action, 'description'):
        return action.description
    else:
        return capfirst(action.__name__.replace('_', ' '))


class BaseListAction(object):

    def __init__(self, request, queryset):
        self.request = request
        self.queryset = queryset
        self.model = queryset.model
        self.options = utils.model_options(self.model)

        self.item_count = len(queryset)

        if self.item_count <= 1:
            objects_name = self.options.verbose_name
        else:
            objects_name = self.options.verbose_name_plural
        self.objects_name = unicode(objects_name)

    @property
    def permission_name(self):
        return None

    def description(self):
        raise NotImplementedError("List action classes require a description attribute.")

    def render_or_none(self):
        """ Returns either:
                Http response (anything)
                None object (shows the list)
        """
        raise NotImplementedError("List action classes require a render_or_none method that returns either a None or HTTP response object.")

    @property
    def template_for_display_nested_response(self):
        """ This is a required attribute for when using the `display_nested_response` method. """
        raise NotImplementedError("List actions classes using display_nested_response require a template")

    def display_nested_response(self):
        """ Utility method when you want to display nested objects
            (such as during a bulk update/delete
        """
        def _format_callback(obj):
            opts = utils.model_options(obj)
            return '%s: %s' % (force_text(capfirst(opts.verbose_name)),
                               force_text(obj))

        collector = utils.NestedObjects(using=None)
        collector.collect(self.queryset)

        context = {
            'queryset': self.queryset,
            'objects_name': self.objects_name,
            'deletable_objects': collector.nested(_format_callback),
        }
        return TemplateResponse(self.request, self.template_for_display_nested_response, context)

    def __call__(self):
        # We check whether the user has permission to delete the objects in the
        # queryset.
        if self.permission_name and not self.request.user.has_perm(self.permission_name):
            message = _("Permission to '%s' denied" % force_text(self.description))
            messages.add_message(self.request, messages.INFO, message)
            return None

        if self.item_count > 0:
            return self.render_or_none()
        else:
            message = _("Items must be selected in order to perform actions on them. No items have been changed.")
            messages.add_message(self.request, messages.INFO, message)
            return None


class DeleteSelectedAction(BaseListAction):
    # TODO: Check that user has permission to delete all related obejcts.  See
    # `get_deleted_objects` in contrib.admin.util for how this is currently
    # done.  (Hint: I think we can do better.)

    description = ugettext_lazy("Delete selected items")

    @property
    def permission_name(self):
        return '%s.delete.%s' \
                % (self.options.app_label, self.options.object_name.lower())

    def render_or_none(self):

        if self.request.POST.get('confirmed'):
            # The user has confirmed that they want to delete the objects.
            num_objects_deleted = len(self.queryset)
            self.queryset.delete()
            message = _("Successfully deleted %d %s" % \
                    (num_objects_deleted, self.objects_name))
            messages.add_message(self.request, messages.INFO, message)
            return None
        else:
            # The user has not confirmed that they want to delete the objects, so
            # render a template asking for their confirmation.
            return self.display_nested_response()

    @property
    def template_for_display_nested_response(self):
        # TODO - power this off the ADMIN2_THEME_DIRECTORY setting
        return "admin2/bootstrap/actions/delete_selected_confirmation.html"


