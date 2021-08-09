import ictv

from ictv.pages import users_page, screens_page, screen_renderer, screen_client, screen_subscriptions_page, screen_router
from ictv.pages import buildings_page, channels_page, channel_page, manage_bundle_page, plugins_page, channel_renderer
from ictv.pages import storage_page, logs_page, emails_page, local_login, utils, shibboleth
from ictv.storage import cache_page, transcoding_page
from ictv.client.pages import client_pages
from ictv.common.utils import get_methods

def init_flask_url_mapping(app):

    if app.config['debug']['dummy_login']:
        app.add_url_rule('/login/<string:email>', view_func=ictv.pages.utils.DummyLogin.as_view('DummyLogin'), methods=get_methods(ictv.pages.utils.DummyLogin))

    if app.config['debug']['debug_env']:
        app.add_url_rule('/debug_env', view_func=ictv.pages.utils.DebugEnv.as_view('DebugEnv'), methods=get_methods(ictv.pages.utils.DebugEnv))

    if 'local' in app.config['authentication']:
        app.add_url_rule('/login', view_func=ictv.pages.local_login.LoginPage.as_view('LoginPage'), methods=get_methods(ictv.pages.local_login.LoginPage))
        app.add_url_rule('/reset', view_func=ictv.pages.local_login.GetResetLink.as_view('GetResetLink'), methods=get_methods(ictv.pages.local_login.GetResetLink))
        app.add_url_rule('/reset/<string:secret>', view_func=ictv.pages.local_login.ResetPage.as_view('ResetPage'), methods=get_methods(ictv.pages.local_login.ResetPage))
        app.add_url_rule('/logout', view_func=ictv.pages.utils.LogoutPage.as_view('LogoutPage'), methods=get_methods(ictv.pages.utils.LogoutPage))

    if 'saml2' in app.config['authentication']:
        app.add_url_rule('/shibboleth', view_func=ictv.pages.shibboleth.Shibboleth.as_view('Shibboleth'), methods=get_methods(ictv.pages.shibboleth.Shibboleth))
        app.add_url_rule('/shibboleth_metadata', view_func=ictv.pages.shibboleth.MetadataPage.as_view('MetadataPage'), methods=get_methods(ictv.pages.shibboleth.MetadataPage))

    app.add_url_rule('/', view_func=ictv.app.IndexPage.as_view('IndexPage'), methods=get_methods(ictv.app.IndexPage))
    app.add_url_rule('/users', view_func=ictv.pages.users_page.UsersPage.as_view('UsersPage'), methods=get_methods(ictv.pages.users_page.UsersPage))
    app.add_url_rule('/users/<int:id>', view_func=ictv.pages.users_page.UserDetailPage.as_view('UserDetailPage'), methods=get_methods(ictv.pages.users_page.UserDetailPage))
    app.add_url_rule('/screens', view_func=ictv.pages.screens_page.ScreensPage.as_view('ScreensPage'), methods=get_methods(ictv.pages.screens_page.ScreensPage))
    app.add_url_rule('/screens/<int:id>', view_func=ictv.pages.screens_page.DetailPage.as_view('ScreensDetailPage'), methods=get_methods(ictv.pages.screens_page.DetailPage))
    app.add_url_rule('/screens/<int:id>/config', view_func=ictv.pages.screens_page.ScreenConfigPage.as_view('ScreenConfigPage'), methods=get_methods(ictv.pages.screens_page.ScreenConfigPage))
    app.add_url_rule('/screens/<int:screen_id>/view/<string:secret>', view_func=ictv.pages.screen_renderer.ScreenRenderer.as_view('ScreenRenderer'), methods=get_methods(ictv.pages.screen_renderer.ScreenRenderer))
    app.add_url_rule('/screens/<int:screen_id>/client/<string:secret>', view_func=ictv.pages.screen_client.ScreenClient.as_view('ScreenClient'), methods=get_methods(ictv.pages.screen_client.ScreenClient))
    app.add_url_rule('/screens/<int:screen_id>/subscriptions', view_func=ictv.pages.screen_subscriptions_page.ScreenSubscriptionsPage.as_view('ScreenSubscriptionsPage'), methods=get_methods(ictv.pages.screen_subscriptions_page.ScreenSubscriptionsPage))
    app.add_url_rule('/screens/redirect/<string:mac>', view_func=ictv.pages.screen_router.ScreenRouter.as_view('ScreenRouter'), methods=get_methods(ictv.pages.screen_router.ScreenRouter))
    app.add_url_rule('/buildings', view_func=ictv.pages.buildings_page.BuildingsPage.as_view('BuildingsPage'), methods=get_methods(ictv.pages.buildings_page.BuildingsPage))
    app.add_url_rule('/channels', view_func=ictv.pages.channels_page.ChannelsPage.as_view('ChannelsPage'), methods=get_methods(ictv.pages.channels_page.ChannelsPage))
    app.add_url_rule('/channels/config/<int:channel_id>', view_func=ictv.pages.channel_page.ChannelPage.as_view('ChannelPage'), methods=get_methods(ictv.pages.channel_page.ChannelPage))
    app.add_url_rule('/channels/config/<int:id>/request/<int:user_id>', view_func=ictv.pages.channel_page.RequestPage.as_view('RequestPage'), methods=get_methods(ictv.pages.channel_page.RequestPage))
    app.add_url_rule('/channels/config/<int:bundle_id>/manage_bundle', view_func=ictv.pages.manage_bundle_page.ManageBundlePage.as_view('ManageBundlePage'), methods=get_methods(ictv.pages.manage_bundle_page.ManageBundlePage))
    app.add_url_rule('/channels/config/<int:channel_id>/subscriptions', view_func=ictv.pages.channel_page.SubscribeScreensPage.as_view('SubscribeScreensPage'), methods=get_methods(ictv.pages.channel_page.SubscribeScreensPage))
    app.add_url_rule('/channel/<int:channel_id>', view_func=ictv.pages.channel_page.DetailPage.as_view('ChannelDetailPage'), methods=get_methods(ictv.pages.channel_page.DetailPage))
    app.add_url_rule('/channel/<int:channel_id>/force_update', view_func=ictv.pages.channel_page.ForceUpdateChannelPage.as_view('ForceUpdateChannelPage'), methods=get_methods(ictv.pages.channel_page.ForceUpdateChannelPage))
    app.add_url_rule('/plugins', view_func=ictv.pages.plugins_page.PluginsPage.as_view('PluginsPage'), methods=get_methods(ictv.pages.plugins_page.PluginsPage))
    app.add_url_rule('/plugins/<int:plugin_id>/config', view_func=ictv.pages.plugins_page.PluginConfigPage.as_view('PluginConfigPage'), methods=get_methods(ictv.pages.plugins_page.PluginConfigPage))
    app.add_url_rule('/preview/channels/<int:channel_id>/<string:secret>', view_func=ictv.pages.channel_renderer.ChannelRenderer.as_view('ChannelRenderer'), methods=get_methods(ictv.pages.channel_renderer.ChannelRenderer))
    app.add_url_rule('/renderer/<int:channelid>', view_func=ictv.pages.utils.DummyRenderer.as_view('DummyRenderer'), methods=get_methods(ictv.pages.utils.DummyRenderer))
    app.add_url_rule('/renderer/<int:channelid>/capsule/<int:capsuleid>', view_func=ictv.pages.utils.DummyCapsuleRenderer.as_view('DummyCapsuleRenderer'), methods=get_methods(ictv.pages.utils.DummyCapsuleRenderer))
    app.add_url_rule('/cache/<int:asset_id>', view_func=ictv.storage.cache_page.CachePage.as_view('CachePage'), methods=get_methods(ictv.storage.cache_page.CachePage))
    app.add_url_rule('/storage', view_func=ictv.pages.storage_page.StoragePage.as_view('StoragePage'), methods=get_methods(ictv.pages.storage_page.StoragePage))
    app.add_url_rule('/storage/<int:channel_id>', view_func=ictv.pages.storage_page.StorageChannel.as_view('StorageChannel'), methods=get_methods(ictv.pages.storage_page.StorageChannel))
    app.add_url_rule('/logs', view_func=ictv.pages.logs_page.LogsPage.as_view('LogsPage'), methods=get_methods(ictv.pages.logs_page.LogsPage))
    app.add_url_rule('/logs/<string:log_name>', view_func=ictv.pages.logs_page.ServeLog.as_view('ServeLog'), methods=get_methods(ictv.pages.logs_page.ServeLog))
    app.add_url_rule('/logas/<string:target_user>', view_func=ictv.pages.utils.LogAs.as_view('LogAs'), methods=get_methods(ictv.pages.utils.LogAs))
    app.add_url_rule('/tour/<string:status>', view_func=ictv.pages.utils.TourPage.as_view('TourPage'), methods=get_methods(ictv.pages.utils.TourPage))
    app.add_url_rule('/client/ks/<path:file>', view_func=ictv.client.pages.client_pages.Kickstart.as_view('Kickstart'), methods=get_methods(ictv.client.pages.client_pages.Kickstart))
    app.add_url_rule('/emails', view_func=ictv.pages.emails_page.EmailPage.as_view('EmailPage'), methods=get_methods(ictv.pages.emails_page.EmailPage))
    app.add_url_rule('/transcoding/<string:b64_path>/progress', view_func=ictv.storage.transcoding_page.ProgressPage.as_view('ProgressPage'), methods=get_methods(ictv.storage.transcoding_page.ProgressPage))
