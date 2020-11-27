import asyncio

import discord
from discord.ext import tasks

from . import utils


class PresenceAutoUpdater(utils.Cog):

    TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    TWITCH_SEARCH_URL = "https://api.twitch.tv/helix/streams"

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self.presence_auto_update_loop.start()
        self.presence_before = None
        self._twitch_app_token = None
        self._refresh_token_task = None
        self.twitch_user_ids = {}  # str: str
        self._user_is_live = False

    def cog_unload(self):
        self.presence_auto_update_loop.cancel()

    async def get_app_token(self, force_refresh:bool=False) -> str:
        """
        Get a valid app token from Twitch
        """

        # See if there's already one set
        if self._twitch_app_token and force_refresh is False:
            return self._twitch_app_token

        # See if there's a config set
        twitch_data = self.bot.config.get("presence", {}).get("streaming", {})
        if not twitch_data:
            return None

        # Grab the token from the API
        self.logger.info("Grabbing a new Twitch.tv app token")
        json = {
            "client_id": twitch_data["twitch_client_id"],
            "client_secret": twitch_data["twitch_client_secret"],
            "grant_type": "client_credentials",
        }
        async with self.bot.session.get(self.TWITCH_TOKEN_URL, json=json) as r:
            data = await r.json()

        # Store it
        self._twitch_app_token = data["access_token"]

        # Set up our refresh task
        async def refresh_token_coro():
            await asyncio.sleep(data["expires_in"] - 60)
            await self.get_app_token(force_refresh=True)
        if self._refresh_token_task:
            self._refresh_token_task.cancel()
        self._refresh_token_task = self.bot.loop.create_task(refresh_token_coro)

        # And return the app token
        return self._twitch_app_token

    async def get_twitch_user_id(self, username:str) -> str:
        """
        Get the user ID for a given Twitch username
        """

        if username in self.twitch_user_ids:
            return self.twich_user_ids[username]
        headers = {
            "Client-Id": self.bot.config.get("presence", {}).get("streaming", {}).get("twitch_client_id", "")
        }
        async with self.bot.session.get("https://api.twitch.tv/helix/users", params={"login": username}, headers=headers) as r:
            data = await r.json()
        self.twitch_user_ids[username] = data["data"][0]["id"]
        return self.twitch_user_ids[username]

    @tasks.loop(seconds=30)
    async def presence_auto_update_loop(self):
        """
        Automatically ping the Twitch servers every 30 seconds and see if we need
        to update the bot's status to the streaming status.
        """

        # See if we should bother doing this
        twitch_data = self.bot.config.get("presence", {}).get("streaming", {})
        if not twitch_data:
            self.logger.info("Disabling stream presence auto update loop")
            self.presence_auto_update_loop.cancel()
            return

        # Grab their username from the config
        twitch_username_url = twitch_data.get("twitch_url", "").strip("/")
        twitch_username = twitch_username_url.split("/")[-1]

        # Get their username
        twitch_user_id = await self.get_twitch_user_id(twitch_username)

        # Get their data from Twitch
        params = {
            "user_id": twitch_user_id,
            "first": 1,
        }
        headers = {
            "Authorization": f"Bearer {await self.get_app_token()}",
            "Client-Id": twitch_data.get("twitch_client_id"),
        }
        async with self.bot.session.get(self.TWITCH_SEARCH_URL, params=params, headers=headers) as r:
            data = await r.json()

        # See if they're live
        try:
            stream_data = data["data"][0]
        except IndexError:
            if self._user_is_live:
                await self.bot.set_default_presence()
                self._user_is_live = False
            return

        # Update the bot's status
        await self.bot.change_presence(
            activity=discord.Streaming(name=stream_data["title"], url=f"https://twitch.tv/{stream_data['user_name']}")
        )
        self._user_is_live = True

    @presence_auto_update_loop.before_loop
    async def presence_auto_update_loop_before_loop(self):
        await self.bot.wait_until_ready()


def setup(bot:utils.Bot):
    x = PresenceAutoUpdater(bot)
    bot.add_cog(x)