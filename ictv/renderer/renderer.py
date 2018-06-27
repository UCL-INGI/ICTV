# -*- coding: utf-8 -*-
#
#    This file belongs to the ICTV project, written by Nicolas Detienne,
#    Francois Michel, Maxime Piraux, Pierre Reinbold and Ludovic Taffin
#    at Université catholique de Louvain.
#
#    Copyright (C) 2016-2018  Université catholique de Louvain (UCL, Belgium)
#
#    ICTV is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    ICTV is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with ICTV.  If not, see <http://www.gnu.org/licenses/>.

import colorsys
import os
import re
import sys
from copy import deepcopy
from html import unescape

import web
import yaml

from ictv import get_root_path
from ictv.common import utils
from ictv.common.utils import deep_update
from ictv.libs.html import HTML
from ictv.plugin_manager.plugin_capsule import PluginCapsule
from ictv.plugin_manager.plugin_slide import PluginSlide


class SlideRenderer(object):
    """ A parameterizable slide renderer. All classes that render slide should extend it. """

    def __init__(self, renderer_globals, app):
        """
            Initializes a slide renderer with the given globals.
            :param renderer_globals: a dictionary in the form
                {
                    '[field-type]': Python function,
                    ...
                }
            Each function is responsible of rendering the corresponding field and will be called by the renderer when
            a corresponding function is parsed in a slide template.
        """
        renderer_globals['get_template_id'] = lambda: utils.generate_secret(digits='')
        self.slide_renderer = web.template.render(os.path.join(get_root_path(), 'renderer/templates/'), globals=renderer_globals)
        self.preview_renderer = web.template.render(os.path.join(get_root_path(), 'renderer'), globals=renderer_globals)
        self.app = app
        super(SlideRenderer, self).__init__()

    def render_slide(self, slide, slide_defaults=None):
        """ Returns the complete HTML element representing the given slide rendered without any outer capsule."""
        if slide_defaults is None:
            slide_defaults = {}
        deep_update(slide_defaults, slide.get_content())
        return self.slide_renderer.base(
            content=(self.slide_renderer.__getattr__(slide.get_template())(slide=slide_defaults)), slide=slide)

    def render_capsule(self, capsule):
        """ Returns the complete HTML element representing the given capsule. """
        content = ""
        capsule_theme = capsule.get_theme()
        if not capsule_theme or capsule_theme not in Themes:
            capsule_theme = self.app.config['default_theme']
        slide_defaults = Themes.get_slide_defaults(capsule_theme)
        for s in capsule.get_slides():
            content += str(self.render_slide(s, deepcopy(slide_defaults)))
        themes = Themes.prepare_for_css_inclusion([capsule_theme])
        return '<section class="%s">%s</section>' % (' '.join(themes), content)

    def render_capsules(self, capsules, context):
        """
            Returns a tuple in the form `content, themes`.
            `content` is the concatenation of the calls of :func:`~renderer.SlideRenderer.render_capsule` over each capsule.
            `themes` is a set of capsule themes.
        """
        if capsules is None or len(capsules) == 0:
            capsules = [get_no_content_capsule(self.app, self.app.config['default_theme'], context)] if self.app.config['default_slides'].get('%s_slide' % context) else []
        content = ''
        themes = set()
        for capsule in capsules:
            if capsule.get_slides():
                themes.add(capsule.get_theme() if capsule.get_theme() in Themes else self.app.config['default_theme'])
                content += self.render_capsule(capsule=capsule)
        return content, themes

    def render_template(self, template_name, content, theme_name):
        """
            Returns the complete HTML element representing the given template filled with the given slide content.
            Theme is added to the slide without any outer capsule.
            :param template_name: The name of the template.
            :param content: The slide content.
            :param theme_name: The name of the theme.
        """
        rendered_content = self.slide_renderer.__getattr__(template_name)(slide=content)
        bg = rendered_content.bg if 'bg' in rendered_content else ''
        themes = Themes.prepare_for_css_inclusion([theme_name])
        return '<section class="%s" %s>%s</section>' % (' '.join(themes), bg, str(rendered_content))

    def preview_slide(self, slide, theme=None, small_size=False):
        """ Returns a full HTML page representing a preview of the given slide. """
        if theme is None:
            themes = []
            slide_defaults = {}
        else:
            themes = Themes.prepare_for_css_inclusion([theme])
            slide_defaults = Themes.get_slide_defaults(theme)
        slide_html = str(self.render_slide(slide, slide_defaults=slide_defaults))
        capsule = '<section class="%s">%s</section>' % (' '.join(themes), str(slide_html))
        return self.preview_renderer.preview(content=capsule, themes=themes, controls=False, small_size=small_size)

    def preview_capsules(self, capsules, context=None, auto_slide=False):
        """ Returns a full HTML page representing a preview of the given capsules. Auto-sliding is disabled. """
        content, themes = self.render_capsules(capsules, context)
        return self.preview_renderer.preview(content=content, themes=themes, auto_slide=auto_slide)

    def render_screen(self, capsules, controls=False, force_page_reloading=False, show_number=False):
        """
            Returns a full HTML page representing a view of the given capsules in the context of a screen.
            Auto-sliding is activated but page reloading is not.
        """
        content, themes = self.render_capsules(capsules, context='screen')
        themes = Themes.prepare_for_css_inclusion(themes)
        return self.preview_renderer.screen(content=content, themes=themes, controls=controls,
                                            force_page_reloading=force_page_reloading, show_number=show_number)

    def render_screen_client(self, screen):
        """
            Return a full HTML page representing the HTML/JS client with smooth reloading and added features in the
            context of a screen.
        """
        return self.preview_renderer.screen_client(url=screen.get_view_link(), show_postit=screen.show_postit)


class ICTVRenderer(SlideRenderer):
    """ The standard slide renderer for ICTV Core. """

    def __init__(self, app):
        renderer_globals = {'title': make_title, 'subtitle': make_subtitle,
                            'img': make_img,
                            'logo': make_logo, 'text': make_text, 'background': make_background}
        super(ICTVRenderer, self).__init__(renderer_globals, app)


class TemplatesMeta(type):
    """ An utility class that constructs dynamically the Templates class. """
    def __init__(self, *args, **kwargs):
        templates = {}
        for template in os.listdir(os.path.join(get_root_path(), 'renderer/templates')):
            if template != 'base.html':
                templates[os.path.splitext(template)[0]] = {}

        for template in templates:
            def f(type):
                def g(*args, **kwargs):
                    id = type + '-' + str(kwargs['number'])
                    templates[template][id] = {'max_chars': kwargs['max_chars']} if 'max_chars' in kwargs else {}
                return g

            dummy_renderer = SlideRenderer({'title': f('title'), 'subtitle': f('subtitle'),
                            'img': f('img'),
                            'logo': f('logo'), 'text': f('text'), 'background': f('background')}, None)

            template_rendered = getattr(dummy_renderer.slide_renderer, template)(slide=None)
            templates[template]['name'] = template_rendered.get('name')
            templates[template]['description'] = template_rendered.get('description')

        self._templates = templates
        super().__init__(self)

    def __getitem__(self, item):
        return self._templates[item]

    def __iter__(self):
        return iter(self._templates)

    def __str__(self):
        return str(self._templates)


class Templates(object, metaclass=TemplatesMeta):
    """
        A dictionary-like class containing all the templates available to render slides. This class has the following form:
        {
            '[template_name]':
            {
                '[field-type]-[field-number]':
                {
                    'max_chars': int  # If applicable to this field type, otherwise empty for now.
                },
            },
            ...
        }
    """
    @classmethod
    def get_non_complying_fields(cls, plugin_slide):
        """
            Returns a list of fields that does not comply with the template chars limits.
            The fields are in the form (id, len_of_text, max_chars_allowed, text)
        """
        content = plugin_slide.get_content()
        template = plugin_slide.get_template()
        non_complying_fields = []
        for id in plugin_slide.get_content():
            if id in cls[template] and 'text' in content[id] and len(remove_html_markup(content[id]['text'])) > cls[template][id]['max_chars']:
                non_complying_fields.append((id, template, len(remove_html_markup(content[id]['text'])), cls[template][id]['max_chars'], content[id]['text']))
        return non_complying_fields


class ThemesMeta(type):
    """ An utility class that constructs dynamically the Themes class. """
    def __init__(self, *args, **kwargs):
        self._themes = {}
        themes = set()
        self._child_themes = {}
        themes_directory = os.path.join(get_root_path(), 'renderer', 'themes')
        for theme in [p for p in os.listdir(themes_directory) if os.path.isdir(os.path.join(themes_directory, p))]:
            try:
                with open(os.path.join(themes_directory, theme, 'config' + os.extsep + 'yaml')) as config_file:
                    config = yaml.load(config_file)
                self._themes[theme] = config
                if 'base_color' in self._themes[theme]:
                    theme_base_color = self._themes[theme]['base_color']
                    theme_base_color = (theme_base_color['h'], theme_base_color['s'], theme_base_color['v'])
                    self._themes[theme]['palette'] = [colorsys.hsv_to_rgb((theme_base_color[0] + (i / 360)) % 1, theme_base_color[1],
                                                   theme_base_color[2]) for i in range(30, 360, 30)]
                    self._themes[theme]['ckeditor_palette'] = ','.join(
                        [''.join('%02X' % round(i * 255) for i in color) for color in self._themes[theme]['palette']]
                    )
                parent = self._themes[theme].get('parent')
                if parent:
                    self._child_themes[parent] = self._child_themes.get(parent, set()) | {theme}
                themes.add(theme)
            except FileNotFoundError:
                print('Theme %s does not have a config.yaml. It will be ignored' % theme, file=sys.stderr)

        def remove_theme(theme):
            if theme in self._child_themes:
                for child in self._child_themes[theme]:
                    print('Theme %s referenced %s as its parent, but %s could not be found. It will be ignored.'
                          % (child, theme, theme), file=sys.stderr)
                    remove_theme(child)
            themes.discard(theme)
            self._themes.pop(theme)

        for parent in self._child_themes.keys():
            if parent not in themes:
                remove_theme(parent)

        themes_static_dir = os.path.join(get_root_path(), 'static', 'themes')
        if not os.path.exists(themes_static_dir):
            os.mkdir(themes_static_dir)

        for theme, config in self._themes.items():
            link_name = os.path.join(themes_static_dir, theme)
            if not os.path.exists(link_name):
                os.symlink(os.path.join(get_root_path(), 'renderer', 'themes', theme, 'assets'), link_name,
                           target_is_directory=True)

        def set_theme_level(theme, level=0):
            if self._themes[theme].get('level', -1) < level:
                self._themes[theme]['level'] = level
                for child in self._child_themes.get(theme, []):
                    set_theme_level(child, level+1)

        for theme in [t for t in self._themes.keys() if self._themes[t].get('parent') is None]:
            set_theme_level(theme)

        super().__init__(self)

    def __getitem__(self, item):
        return self._themes[item]

    def __iter__(self):
        return iter(self._themes)

    def __str__(self):
        return str(self._themes)

    def __contains__(self, item):
        return item in self._themes

    def items(self):
        return self._themes.items()

    def get_children_of(cls, theme):
        return cls._child_themes.get(theme, [])


class Themes(object, metaclass=ThemesMeta):
    """
        A dictionary-like class containing all the themes available to render slides. This class has the following form:
        {
            '[theme_name]': A dictionary containing the data loaded from the theme config file
            ...
        }
    """
    @classmethod
    def recurse_up_parentship(cls, theme):
        """ Yields all the parents of the given theme. The closest parent of the given theme is yielded first. """
        parent = cls[theme].get('parent')
        if parent:
            yield parent
            yield from cls.recurse_up_parentship(parent)

    @classmethod
    def order_themes(cls, themes, check_css=True):
        """
            Returns an ordered list of an iterable of themes according to their number of parents in ascending order.
            Based on check_css, it will also filter out themes that have no css or not.
        """
        return sorted(filter(lambda x: not check_css or cls[x]['css'], list(themes)), key=lambda t: cls[t]['level'])

    @classmethod
    def prepare_for_css_inclusion(cls, themes):
        """ Check for any parent that should be included first for each theme, filter duplicated themes and order them. """
        filtered_themes = set(themes)
        for theme in themes:
            filtered_themes |= set(cls.recurse_up_parentship(theme))
        return cls.order_themes(filtered_themes)

    @classmethod
    def get_slide_defaults(cls, theme):
        """
            Returns the default values of slide elements based on the given theme and its parents
        """
        parent = cls[theme].get('parent')
        if parent:
            defaults = cls.get_slide_defaults(parent)
            deep_update(defaults, cls[theme].get('slide_defaults', {}))
        else:
            defaults = cls[theme].get('slide_defaults', {})
        return deepcopy(defaults)

    @classmethod
    def get_sorted_themes(cls):
        themes = []

        def add_theme(theme):
            themes.append((theme, cls[theme]))
            for child in cls.get_children_of(theme):
                add_theme(child)

        level_zero_themes = sorted([t for t in cls if cls[t]['level'] == 0])
        for t in level_zero_themes:
            add_theme(t)

        return themes


def make_title(**kwargs):
    if 'content' in kwargs and 'number' in kwargs:
        id = 'title-' + str(kwargs['number'])
        text = kwargs['content'][id]['text']
        h = HTML()
        h.h1(text, klass='title')
        return str(h)


def make_subtitle(**kwargs):
    if 'content' in kwargs and 'number' in kwargs:
        id = 'subtitle-' + str(kwargs['number'])
        text = kwargs['content'][id]['text']
        h = HTML()
        h.h4(text, klass='subtitle')
        return str(h)


def make_img(**kwargs):
    if 'content' in kwargs and 'number' in kwargs:
        id = 'image-' + str(kwargs['number'])
        src = kwargs['content'].get(id, {}).get('src')
        h = HTML()
        if src:
            if 'style' in kwargs.keys():
                h.img(src=src, klass='sub-image', style=kwargs['style'])
            else:
                h.img(src=src, klass='sub-image')
        return str(h)


def make_logo(**kwargs):
    if 'content' in kwargs and 'number' in kwargs:
        id = 'logo-' + str(kwargs['number'])
        src = kwargs['content'].get(id, {}).get('src')
        h = HTML()
        if src:
            h.img(src=src)
        return str(h)


def make_text(**kwargs):
    if 'content' in kwargs and 'number' in kwargs:
        id = 'text-' + str(kwargs['number'])
        text = kwargs['content'][id]['text']
        wrap_in_div = kwargs['wrap_in_div'] if 'wrap_in_div' in kwargs else True
        if wrap_in_div:
            h = HTML()
            h.div(text, klass='text', style=kwargs.get('style') or 'text-align: justify;', escape=False)
            rendered = str(h)
        else:
            rendered = text

        return rendered


def make_background(**kwargs):
    if 'content' in kwargs and 'number' in kwargs:
        id = 'background-' + str(kwargs['number'])
        if 'src' in kwargs['content'].get(id, {}):
            src = kwargs['content'][id]['src']
            size = kwargs['content'][id]['size']
            color = kwargs['content'][id]['color'] if 'color' in kwargs['content'][id] else 'black'
            attrs = 'data-background-image="' + src + '" data-background-size="' + size + '" data-background-color="' + color + '"'
        elif 'iframe' in kwargs['content'][id]:
            attrs = 'data-background-iframe="' + '/static/' + kwargs['content'][id]['iframe'] + '"'
        elif 'video' in kwargs['content'][id]:
            attrs = 'data-background-video="%s"' % kwargs['content'][id]['video']
        else:
            return ''
        return attrs


def get_no_content_capsule(app, theme, context):
    slide = app.config['default_slides']['%s_slide' % context]

    def get_no_content_slide():
        return type("NoContentSlide", (PluginSlide, object),
                    {'get_duration': lambda: slide['duration'], 'get_content': lambda: slide['content'],
                     'get_template': lambda: slide['template']})

    return type("NoContentCapsule", (PluginCapsule, object),
                {'get_slides': lambda: [get_no_content_slide()], 'get_theme': lambda: theme})


def remove_html_markup(text):
    remove_tags = re.compile(r'<.*?>')
    return unescape(remove_tags.sub('', text))
