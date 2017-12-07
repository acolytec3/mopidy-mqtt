# future imports
from __future__ import absolute_import
from __future__ import unicode_literals

# stdlib imports
import logging
import time
import json

from mopidy import core

import paho.mqtt.client as mqtt

# third-party imports
import pykka

logger = logging.getLogger(__name__)

class MQTTFrontend(pykka.ThreadingActor, core.CoreListener):

    def __init__(self, config, core):
        logger.info("mopidy_mqtt initializing ... ")
        self.core = core
        self.mqttClient = mqtt.Client(client_id="mopidy-" + str(int(round(time.time() * 1000))), clean_session=True)
        self.mqttClient.on_message = self.mqtt_on_message
        self.mqttClient.on_connect = self.mqtt_on_connect     
        
        self.config = config['mqtthook']
        self.topic = self.config['topic']
        self.json_state = self.config['json_state']

        if self.config['username'] and self.config['password']:
            self.mqttClient.username_pw_set(self.config['username'], password=self.config['password'])

        host = self.config['mqtthost']
        port = self.config['mqttport']

        self.mqttClient.connect_async(host, port, 60)        
        
        self.mqttClient.loop_start()
        super(MQTTFrontend, self).__init__()
        self.MQTTHook = MQTTHook(self, core, config, self.mqttClient)
        
    def mqtt_on_connect(self, client, userdata, flags, rc):
        logger.info("Connected with result code %s" % rc)
        
        rc = self.mqttClient.subscribe(self.topic + "/play")
        if rc[0] != mqtt.MQTT_ERR_SUCCESS:            
            logger.warn("Error during subscribe: " + str(rc[0]))
        else:
            logger.info("Subscribed to " + self.topic + "/play")
        self.mqttClient.subscribe(self.topic + "/control")
        logger.info("sub:" + self.topic + "/control")
        self.mqttClient.subscribe(self.topic + "/volume")
        logger.info("sub:" + self.topic + "/volume")

    		## Listen for request to refresh all data
        self.mqttClient.subscribe(self.topic + "/current_state")

    def mqtt_on_message(self, mqttc, obj, msg):
        logger.info("received a message on " + msg.topic+" with payload "+str(msg.payload))
        topPlay = self.topic + "/play"
        topControl = self.topic + "/control"
        topVolume = self.topic + "/volume"
        topCurrentState = self.topic + "/current_state"

        if msg.topic == topPlay:
            self.core.tracklist.clear()
            self.core.tracklist.add(None, None, str(msg.payload), None)
            self.core.playback.play()
        elif msg.topic == topControl:
            if msg.payload == "stop":
                self.core.playback.stop()
            elif msg.payload == "pause":
                self.core.playback.pause()
            elif msg.payload == "play":
                self.core.playback.play()
            elif msg.payload == "resume":
                self.core.playback.resume()
            elif msg.payload == "next":
                self.core.playback.next()
            elif msg.payload == "previous":
                self.core.playback.previous()
        elif msg.topic == topVolume:
            try:
                volume=int(msg.payload)
                self.core.mixer.set_volume(volume)
            except ValueError:
                logger.warn("invalid payload for volume: " + msg.payload)
        elif msg.topic == topCurrentState:
			      # Publish the current state
            self.send_state()

    def send_state(self):
        current_track = self.core.playback.get_current_track().get()
        playback_state = self.core.playback.get_state().get()

        current_state = {
            "playback": playback_state,
            "timestamp": int(time.time())
        }
        if current_track:
          track_artist = list(current_track.artists)[0].name
          track_name = current_track.name
          track_uri = current_track.uri
          # {'tunein:station:s115770': (Image(uri='http://cdn-radiotime-logos.tunein.com/s115770q.png'),)}
          images = []
          imgUris = self.core.library.get_images([track_uri]).get()
          for k in imgUris:
            images.append(imgUris[k][0].uri)
      
          image = None
          if len(images) > 0:
            image = images[0]

          current_state.update({
            "artist":track_artist,
            "name": track_name,
            "uri": track_uri,
            "image": image,
          })
          logger.info(current_state) 
        else:
          logger.info("Failed to get current track")
        self.MQTTHook.publish("/status",  current_state)

    def on_stop(self):
        logger.info("mopidy_mqtt shutting down ... ")
        self.mqttClient.disconnect()
        
    #def stream_title_changed(self, title):
    #    self.send_state()
        #if self.json_state:  title = {"title": title}
        #self.MQTTHook.publish("/nowplaying", title)

    def playback_state_changed(self, old_state, new_state):
        self.send_state()
        #payload = new_state
        #if self.json_state:
        #    payload = {"old_state": old_state, "new_state": new_state}
        #self.MQTTHook.publish("/state", payload)
        #if (new_state == "stopped" and not self.json_state):
        #    self.MQTTHook.publish("/nowplaying", "stopped")
        
    #def track_playback_started(self, tl_track):
    #    self.send_state()
        #track = tl_track.track
        #artists = ', '.join(sorted([a.name for a in track.artists]))
        #payload = artists + ":" + track.name
        #if self.json_state:
        #    payload = {"title": track.name, "artist": artists}
        #self.MQTTHook.publish("/nowplaying", payload)
        #try:
        #    album = track.album
        #    payload = next(iter(album.images))
        #    if self.json_state: 
        #        payload = {"image_url": albumImage}
        #    self.MQTTHook.publish("/image", payload)
        #except:
        #    logger.debug("no image")
        
class MQTTHook():
    def __init__(self, frontend, core, config, client):
        self.config = config['mqtthook']
        self.mqttclient = client

    def publish(self, topic, state):
        full_topic = self.config['topic'] + topic
        try:
            state = json.dumps(state)
            rc = self.mqttclient.publish(full_topic, state)
            if rc[0] == mqtt.MQTT_ERR_NO_CONN:            
                logger.warn("Error during publish: MQTT_ERR_NO_CONN")
            else:
                logger.info("Sent " + state + " to " + full_topic)
        except Exception as e:
            logger.error('Unable to send', exc_info=True) 
