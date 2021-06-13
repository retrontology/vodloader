# vodloader
Capture Twitch streams to be uploaded to YouTube.


## Install
All you need to do is clone this repo and install the python requirements.
```
git clone https://github.com/retrontology/vodloader
cd vodloader
pip install -r requirements.txt
```

## Config
You need to set up your config file before you run the program so it knows what channel(s) you want to archive.

* **twitch**:
  * **client_id**: The client ID of your registered Twitch application to interface with the Twitch API. This is received from the [Twitch Developer Portal](https://dev.twitch.tv/console/apps).
  * **client_secret**: The client secret of your registered Twitch application to interface with the Twitch API. This is received from the [Twitch Developer Portal](https://dev.twitch.tv/console/apps).
  * **channels**:
    * **Some_Channel_Name**: This is where you put the name of the Twitch channel you want to archive. You may make multiple entries for multiple channels, but there must be a youtube_param child for each one.
      * **backlog**: (True/False) Whether you want to upload the current VOD backlog available on Twitch (currently expiremental support so use at your own risk)
      * **chapters**: ("games"/"titles"/False) Create chapters for YouTube based on either game or title changes. Can be set to False to disable
      * **quality**: The stream quality to be passed to streamlink for downloading. Can be left blank and will default to "best"
      * **timezone**: The time zone of the streamer to localize the time for the time formatted titles and descriptions. If left blank will default to UTC
      * **youtube_param**: These are details that are sent to YouTube to help define and classify your upload.
        * **title**: A title format to be displayed on the uploaded video. See [format_chart.md](https://github.com/retrontology/vodloader/blob/main/format_chart.md) for formatting
        * **description**: A description format to be listed below the uploaded video. See [format_chart.md](https://github.com/retrontology/vodloader/blob/main/format_chart.md) for formatting
        * **categoryId**: A number that designates what YouTube category the video belongs in.
        * **playlistId**: The ID of a playlist that the uploaded video will be inserted into. Can be left blank
        * **privacy**: The privacy status the video will be listed as. The current possible values are "private", "unlisted", and "public".
        * **tags**: Tags that will aid in searching for the video.
          * "Some Tag"
          * "Some Other Tag"
   * **webhook**
     * **host**: The domain/address of the host machine.
     * **port**: Some arbitrary port that the webhook client will listen on. Ideally >= 1024
     * **ssl_cert**: The ssl certificate file for your HTTPS server. **It needs to not be self-signed and for the correct domain/address or the webhook will not work!** I recommend using [Let's Encrypt](https://letsencrypt.org/) to obtain a free certificate.
     * **ssl_key**: The ssl private keyfile for your HTTPS server.
* **youtube**:
  * **upload**: (True/False) Whether you want to upload to YouTube or not
  * **json**: The json file that holds the OAuth 2 secrets generated from the [Google Developer Console](https://console.cloud.google.com/apis/credentials)
  * **sort**: (True/False) Whether you want to sort the playlist or not. Only works if a playlist is specified and the videos in the playlist are only uploaded by vodloader.
* **download**:
  * **keep**: (True/False) Whether you want to keep the downloads or delete them after they're uploaded
  * **directory**: Where you want to store the downloaded videos before they are uploaded. Can be left blank and will default to the video folder.
  * **quota_pause**: Whether or not you want to pause downloading the backlog while waiting for the YouTube quota to reset


## Usage
```
python run.py [-h] [-c config.yaml] [-d]

optional arguments:
  -h, --help            show this help message and exit
  -c config.yaml, --config config.yaml
  -d, --debug
```