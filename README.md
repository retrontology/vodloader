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
      * **youtube_param**: These are details that are sent to YouTube to help define and classify your upload.
        * **description**: A description to be listed below the video.
        * **categoryId**: A number that designates what YouTube category the video belongs in.
        * **privacy**: The privacy status the video will be listed as. The current possible values are "private", "unlisted", and "public".
        * **tags**: Tags that will aid in searching for the video.
          * "Some Tag"
          * "Some Other Tag"
   * **webhook**
     * **host**: The domain/address of the host machine.
     * **port**: Some arbitrary port that the webhook client will listen on. Ideally >= 1024
     * **ssl_port**: Some arbitrary port that the HTTPS server will listen on to reverse proxy back to the webhook port. Needs to be different than the webhook client port and also ideally >=1024. If you're behind a router you will need to forward this port to your host machine.
     * **ssl_cert**: The ssl certificate file for your HTTPS server. **It needs to not be self-signed and for the correct domain/address or the webhook will not work!** I recommend using [Let's Encrypt](https://letsencrypt.org/) to obtain a free certificate.
* **youtube**:
  * **json**: The json file that holds the OAuth 2 secrets generated from the [Google Developer Console](https://console.cloud.google.com/apis/credentials)
* **download**:
  * **directory**: Where you want to store the downloaded videos before they are uploaded. Can be left blank and will default to the video folder.


## Running
```python run.py```
