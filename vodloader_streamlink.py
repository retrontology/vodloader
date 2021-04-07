from streamlink.plugins import twitch
from streamlink.session import Streamlink
from streamlink.exceptions import StreamError, PluginError
from streamlink.utils.times import hours_minutes_seconds
from streamlink.session import Streamlink
from streamlink.logger import StreamlinkLogger
import logging

logging.setLoggerClass(StreamlinkLogger)
log = logging.getLogger('Streamlink')

class FixedTwitchHLSStreamWorker(twitch.TwitchHLSStreamWorker):
    def iter_segments(self):
        total_duration = 0
        error_count = 0
        while not self.closed:
            for sequence in filter(self.valid_sequence, self.playlist_sequences):
                log.debug(f"Adding segment {sequence.num} to queue")
                yield sequence
                total_duration += sequence.segment.duration
                if self.duration_limit and total_duration >= self.duration_limit:
                    log.info(f"Stopping stream early after {self.duration_limit}")
                    return

                # End of stream
                stream_end = self.playlist_end and sequence.num >= self.playlist_end
                if self.closed or stream_end:
                    return

                self.playlist_sequence = sequence.num + 1

            if self.wait(self.playlist_reload_time):
                try:
                    self.reload_playlist()
                    error_count = 0
                except StreamError as err:
                    log.warning(f"Failed to reload playlist: {err}")
                    error_count += 1
                    log.warning(f"Error #{error_count}")
                    if error_count > 8:
                        self.close()

class FixedTwitchHLSStreamReader(twitch.TwitchHLSStreamReader):
    __worker__ = FixedTwitchHLSStreamWorker
    __writer__ = twitch.TwitchHLSStreamWriter
    
class FixedTwitchHLSStream(twitch.TwitchHLSStream):
    __reader__ = FixedTwitchHLSStreamReader

class FixedTwitch(twitch.Twitch):
    def _get_hls_streams(self, url, restricted_bitrates, **extra_params):
        time_offset = self.params.get("t", 0)
        if time_offset:
            try:
                time_offset = hours_minutes_seconds(time_offset)
            except ValueError:
                time_offset = 0

        try:
            streams = FixedTwitchHLSStream.parse_variant_playlist(self.session, url, start_offset=time_offset, **extra_params)
        except OSError as err:
            err = str(err)
            if "404 Client Error" in err or "Failed to parse playlist" in err:
                return
            else:
                raise PluginError(err)

        for name in restricted_bitrates:
            if name not in streams:
                log.warning("The quality '{0}' is not available since it requires a subscription.".format(name))

        return streams

class FixedStreamlink(Streamlink):

    def streams(self, url, **params):
        plugin = FixedTwitch(url)
        return plugin.streams(**params)
    
    def resolve_url(self, url, follow_redirect=True):
        """Attempts to find a plugin that can use this URL.
        The default protocol (http) will be prefixed to the URL if
        not specified.
        Raises :exc:`NoPluginError` on failure.
        :param url: a URL to match against loaded plugins
        :param follow_redirect: follow redirects
        """
        return FixedTwitch(url)