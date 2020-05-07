#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# Snips Lights + Homeassistant
# -----------------------------------------------------------------------------
# Copyright 2019 Patrick Fial
# -----------------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------

import requests
import logging
from os import environ

from hss_skill import hss

# -----------------------------------------------------------------------------
# global definitions (home assistant service URLs)
# -----------------------------------------------------------------------------

HASS_LIGHTS_ON_SVC = "/api/services/light/turn_on"
HASS_LIGHTS_OFF_SVC = "/api/services/light/turn_off"
HASS_GROUP_ON_SVC = "/api/services/homeassistant/turn_on"
HASS_GROUP_OFF_SVC = "/api/services/homeassistant/turn_off"
HASS_AUTOMATION_ON_SVC = "/api/services/automation/turn_on"
HASS_AUTOMATION_OFF_SVC = "/api/services/automation/turn_off"

# -----------------------------------------------------------------------------
# class App
# -----------------------------------------------------------------------------

class Skill(hss.BaseSkill):

    # -------------------------------------------------------------------------
    # ctor

    def __init__(self):
        super().__init__()

        self.enable_confirmation = False

        self.my_intents = ['s710:keepLightOn', 's710:turnOnLight', 's710:keepLightOff', 's710:turnOffLight', 's710:enableAutomatic', 's710:enableAutomaticOff']

        # try to use HASSIO token via environment variable & internal API URL in case no config.ini parameters are given

        if 'hass_token' in self.config['skill']:
            self.hass_token = self.config['skill']['hass_token']
        elif 'HASSIO_TOKEN' in environ:
            self.hass_token = environ['HASSIO_TOKEN']

        if 'hass_host' in self.config['skill']:
            self.hass_host = self.config['skill']['hass_host']
        elif self.hass_token is not None and 'HASSIO_TOKEN' in environ:
            self.hass_host = 'http://hassio/homeassistant/api'

        self.hass_headers = { 'Content-Type': 'application/json', 'Authorization': "Bearer " + self.hass_token }

        if 'confirmation_success' in self.config['skill']:
            self.confirmation_success = self.config['skill']['confirmation_success']
        else:
            self.confirmation_success = "Okay"

        if 'confirmation_failure' in self.config['skill']:
            self.confirmation_failure = self.config['skill']['confirmation_failure']
        else:
            self.confirmation_failure = "Fehler"

        if 'enable_confirmation' in self.config['skill'] and self.config['skill']['enable_confirmation'] == "True":
            self.enable_confirmation = True

    # --------------------------------------------------------------------------
    # get_intentlist (overwrites BaseSkill.get_intentlist)
    # --------------------------------------------------------------------------

    def get_intentlist(self):
        return self.my_intents

    # --------------------------------------------------------------------------
    # handle (overwrites BaseSkill.handle)
    # --------------------------------------------------------------------------

    def handle(self, request, session_id, site_id, intent_name, slots):
        room_id = slots["room_id"] if "room_id" in slots else None
        lamp_id = slots["lamp_id"] if "lamp_id" in slots else None
        brightness = slots["brightness"] if "brightness" in slots else None

        if room_id:
            room_id = room_id.lower().replace('ä', 'ae').replace('ü','ue').replace('ö', 'oe')

        # get corresponding home assistant service-url + payload

        service, data = self.params_of(room_id, lamp_id, site_id, brightness, intent_name)

        if not service or not data:
            self.log.error("Service/service data could not be determined")
            return self.done(session_id, site_id, intent_name, "Aktion konnte nicht durchgeführt werden", "de_DE")

        # fire the service using HA REST API

        if self.debug:
            self.logger.debug("Intent {}: Firing service [{} -> {}] with [{}]".format(intent_name, self.hass_host, service, data))

        r = requests.post(self.hass_host + service, json = data, headers = self.hass_headers)

        if r.status_code != 200:
            return self.done(session_id, site_id, intent_name, "Aktion konnte nicht durchgeführt werden", "de_DE")

        # second additional service? (keep light on = disable automation + turn on light)

        if intent_name == 's710:keepLightOn':
            service, data = self.params_of(room_id, lamp_id, site_id, brightness, "s710:turnOnLight")

            r = requests.post(self.hass_host + service, json = data, headers = self.hass_headers)

        elif intent_name == 's710:keepLightOff':
            service, data = self.params_of(room_id, lamp_id, site_id, brightness, "s710:turnOffLight")

            r = requests.post(self.hass_host + service, json = data, headers = self.hass_headers)

        elif intent_name == 's710:enableAutomatic':
            service, data = self.params_of(room_id, lamp_id, site_id, brightness, "s710:enableAutomaticOff")

            r = requests.post(self.hass_host + service, json = data, headers = self.hass_headers)

        response_message = None

        if self.enable_confirmation and r.status_code == 200:
            response_message = self.confirmation_success
        elif self.enable_confirmation:
            response_message = self.confirmation_failure

        return self.done(session_id, site_id, intent_name, response_message, "de_DE")

    # -------------------------------------------------------------------------
    # params_of

    def params_of(self, room_id, lamp_id, site_id, brightness, intent_name):

        # turn on/off lights

        if intent_name == 's710:turnOnLight':
            if lamp_id is not None:
                return (HASS_LIGHTS_ON_SVC, {'entity_id': 'light.{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_GROUP_ON_SVC, {'entity_id': 'group.lights_{}'.format(room_id) })
            else:
                return (HASS_GROUP_ON_SVC, {'entity_id': 'group.lights_{}'.format(site_id) })

        if intent_name == 's710:turnOffLight':
            if lamp_id is not None:
                return (HASS_LIGHTS_OFF_SVC, {'entity_id': 'light.{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_GROUP_OFF_SVC, {'entity_id': 'group.lights_{}'.format(room_id) })
            else:
                return (HASS_GROUP_OFF_SVC, {'entity_id': 'group.lights_{}'.format(site_id) })

        # control all lights

        if intent_name == 's710:turnOnAllLights':
            return (HASS_GROUP_ON_SVC, {'entity_id': 'group.all_lights' })

        if intent_name == 's710:turnOffAllLights':
            return (HASS_GROUP_OFF_SVC, {'entity_id': 'group.all_lights' })

        # keep lights on/off (via automation enable/disable + light on/off)

        if intent_name == 's710:keepLightOn':
            if lamp_id is not None:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_off_{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_off_{}'.format(room_id) })
            else:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_off_{}'.format(site_id) })

        if intent_name == 's710:keepLightOff':
            if lamp_id is not None:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_on_{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_on_{}'.format(room_id) })
            else:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_on_{}'.format(site_id) })

        if intent_name == 's710:enableAutomatic':
            if lamp_id is not None:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_on_{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_on_{}'.format(room_id) })
            else:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_on_{}'.format(site_id) })

        if intent_name == 's710:enableAutomaticOff':
            if lamp_id is not None:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_off_{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_off_{}'.format(room_id) })
            else:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_off_{}'.format(site_id) })

        # set light brightness

        if intent_name == 's710:setLightBrightness':
            if lamp_id is not None and brightness is not None:
                return (HASS_LIGHTS_ON_SVC, {'entity_id': 'light.{}'.format(lamp_id), 'brightness': brightness })

        return (None, None)

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    App()
