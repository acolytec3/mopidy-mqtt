# This repository is deprecated.  I am no longer maintaining this.
# Features

This is a fork of a Mopidy Frontend Extension that allows you to control Mopidy with MQTT and retrieve some information from Mopidy via MQTT.
This version is specifically aimed at integrating with the Snips voice assistant.  Currently can start and stop play back, move to next song or go back to previous, and play specific songs or start an artist playlist.  

Changes from original version:
* You must use json for the incoming message payloads to be recognized by the extension.  Using strings as your message payloads will break the play song and artist messages.
* For each action you want to take, you have to put the appropriate MQTT topic in both the on_connect and on_message locations corresponding to the action you want the frontend to take.
* For song/artist playback, the extension now uses the search feature built into Mopidy instead of expecting a URI in the message payload.  See details below.

## Status update

Mopidy sends an update as soon the playback state changes:

`mytopic/state -> 'paused'`

When a new title or stream is started Mopidy sends this via `nowplaying`

`mytopic/nowplaying -> 'myradio'`

## Play a song or artist radio
You can start playback of a song or stream via MQTT. Send the below.  Note, this requires json input.  Look at the code to see what your slot names need to be for song and artist.

`mytopic/playSong -> song: "Yellow Submarine", artist: "Beatles" (artist is optional- but helpful for locating the exact song you want)
 mytopic/playArtist -> artist: "Beatles"

## Stop playback
You can stop the playback via MQTT. Send the following:

`mytopic/control -> 'stop'`


# Installation

This is an example how to install on a Raspi:

```
cd ~
git clone https://github.com/magcode/mopidy-mqtt.git
cd mopidy-mqtt
sudo python setup.py develop
```

Now configure the following file: `/etc/mopidy/mopidy.conf`

```
[mqtthook]
enabled = true
mqtthost = <mqtt host>
mqttport = <mqtt port>
username = <mqtt username> (Optional)
password = <mqtt password> (Optional)
topic = <topic, e.g. home/livingroom/music>
json_state = false (mqtt state will be a json struct instead of a string)
```

Restart Mopidy with `sudo service mopidy restart`

To check Mopidy log run `sudo tail -f /var/log/mopidy/mopidy.log`


# To dos
1) Fix volume control.  Currently broken.
2) Figure out how to move each message topic to a config value in the Mopidy config file.
