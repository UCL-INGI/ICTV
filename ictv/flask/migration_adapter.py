import flask
from flask import Flask, session
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound
from jinja2 import Environment,FileSystemLoader

# Allows the use of the old rendering syntax previously used in web.py
class render_jinja:

    def __init__(self, *a, **kwargs):
        extensions = kwargs.pop('extensions', [])
        globals = kwargs.pop('globals', {})

        self._lookup = Environment(loader=FileSystemLoader(*a, **kwargs), extensions=extensions)
        self._lookup.globals.update(globals)

    def __getattr__(self, name):
        path = name + '.html'
        t = self._lookup.get_template(path)
        return t.render

class Storage(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as k:
            raise AttributeError(k)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError as k:
            raise AttributeError(k)

    def __repr__(self):
        return "<Storage " + dict.__repr__(self) + ">"

class FrankenFlask(Flask):

    def __init__(self,name):
        super().__init__(name)
        self.session = session
        self.plugins = {}
        self.pre_processors = []
        self.post_processors = []
        self.error_handlers = []
        self.appset = set()

    def register_plugin(self,route,app):
        """
            Register sub applications to provision the dispatcher.
        """
        # Copying the ictv_app config
        tmp_config = self.config.copy()
        tmp_config.update(app.config)
        app.config = tmp_config

        # Copying the plugin manager
        app.plugin_manager = self.plugin_manager

        # Copying the slide renderer
        app.ictv_renderer = self.ictv_renderer

        # Needed in editor to transcode video uploaded
        app.transcoding_queue = self.transcoding_queue

        # Duplicating the secret_key to make the session accessible
        # WARN: MUST be the same as self.secret_key
        app.secret_key = self.secret_key

        # Registering and applying all processors to the new subapp
        # This is necessary when adding a new sub-app in runtime
        if app not in self.appset:
            for proc in self.pre_processors:
                if (proc["cascade"]):
                    app.register_before_request(proc["factory"],proc["cascade"],proc["needs_app"])

            for proc in self.post_processors:
                if (proc["cascade"]):
                    app.register_after_request(proc["factory"],proc["cascade"],proc["needs_app"])

            for proc in self.error_handlers:
                if (proc["cascade"]):
                    app.prepare_error_handler(proc["error"],proc["handler_factory"],proc["cascade"],proc["needs_app"])

            app.apply_error_handlers()
            app.apply_pre_processors()
            app.apply_post_processors()


        self.plugins[route] = app
        self.appset.add(app)

    def get_app_dispatcher(self):
        """
            Initialize the dispatcher with the default app
            and the plugin sub-apps as mounts with
            specific root paths in their urls
        """

        # Applying the processors to the current app instance
        self.apply_pre_processors()
        self.apply_post_processors()
        self.apply_error_handlers()

        # It appears that there must be at least one mount when starting
        # in order to allow adding new mounts during runtime
        self.plugins.update({"/notfound":NotFound()})

        dispatcher = DispatcherMiddleware(self,self.plugins)
        dispatcher.config = self.config
        return dispatcher

    def register_before_request(self,factory,cascade=False,needs_app=False):
        """
            Save preprocessors factories in order to apply them
            with app.apply_pre_processors().
            @params : - function factory: processor factory
                      - bool cascade: whether this must be applied to the plugins
                      - bool needs_app: whether the factory needs the app instance

        """
        self.pre_processors.append({"factory":factory,"cascade":cascade,"needs_app":needs_app,"applied":False})
        if (cascade):
            for value in self.appset:
                value.register_before_request(factory,cascade,needs_app)

    def register_after_request(self,factory,cascade=False,needs_app=False):
        """
            Save postprocessors factories in order to apply them with
            app.apply_post_processors().
            @params : - function factory: processor factory
                      - bool cascade: whether this must be applied to the plugins
                      - bool needs_app: whether the factory needs the app instance

        """
        self.post_processors.append({"factory":factory,"cascade":cascade,"needs_app":needs_app,"applied":False})
        if (cascade):
            for value in self.appset:
                value.register_after_request(factory,cascade,needs_app)

    def prepare_error_handler(self,error,factory,cascade=True,needs_app=False):
        """
            Save error handlers in order to register them
            with app.register_error_handler().
            @params : - Exception error: the error to be handled
                      - func handler: the handler factory
                      - bool cascade: whether this must be applied to the plugins
                      - bool needs_app: whether the factory needs the app instance

        """
        self.error_handlers.append({"error":error,"cascade":cascade,"handler_factory":factory, "needs_app":needs_app, "applied":False})
        if (cascade):
            for value in self.appset:
                value.prepare_error_handler(error,factory,cascade,needs_app)

    def apply_pre_processors(self):
        """
            Calls the before_request for each app instance
        """
        for proc in self.pre_processors:
            # Prevent from applying twice the same processor
            if (not proc["applied"]):
                proc["applied"]=True
                self.before_request(proc["factory"]() if not proc["needs_app"] else proc["factory"](self))

            for value in self.appset:
                value.apply_pre_processors()

    def apply_post_processors(self):
        """
            Calls the after_request for each app instance
        """
        for proc in self.post_processors:
            # Prevent from applying twice the same processor:
            if (not proc["applied"]):
                proc["applied"]=True
                self.after_request(proc["factory"]() if not proc["needs_app"] else proc["factory"](self))

            for value in self.appset:
                value.apply_post_processors()

    def apply_error_handlers(self):
        """
            Calls the register_error_handler for each app instance
        """
        for proc in self.error_handlers:
            # Prevent from applying twice the same processor
            if (not proc["applied"]):
                proc["applied"]=True
                self.register_error_handler(proc["error"],proc["handler_factory"]() if not proc["needs_app"] else proc["handler_factory"](self))

            for value in self.appset:
                value.apply_error_handlers()
