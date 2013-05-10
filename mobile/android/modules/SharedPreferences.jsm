// -*- Mode: js2; tab-width: 2; indent-tabs-mode: nil; js2-basic-offset: 2; js2-skip-preprocessor-directives: t; -*-
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */
"use strict";

this.EXPORTED_SYMBOLS = ["SharedPreferences"];

const { classes: Cc, interfaces: Ci, utils: Cu } = Components;

// For adding observers.
Cu.import("resource://gre/modules/Services.jsm");

function sendMessageToJava(aMessage) {
  return Cc["@mozilla.org/android/bridge;1"].getService(Ci.nsIAndroidBridge).
    handleGeckoMessage(JSON.stringify(aMessage));
}

/**
 * Create an interface to an Android SharedPreferences branch.
 *
 * branch {String} should be a string describing a preferences branch,
 * like "UpdateService" or "background.data", or null to access the
 * default preferences branch for the application.
 */
function SharedPreferences(branch) {
  if (!(this instanceof SharedPreferences)) {
    return new SharedPreferences(branch);
  }
  this._branch = branch || null;
  this._observers = {};
};

SharedPreferences.prototype = {
  _set: function _set(prefs) {
    sendMessageToJava({
      type: "SharedPreferences:Set",
      preferences: prefs,
      branch: this._branch,
    });
  },

  _setOne: function _setOne(aPrefName, aValue, aType) {
    let prefs = [];
    prefs.push({
      name: aPrefName,
      value: aValue,
      type: aType,
    });
    this._set(prefs);
  },

  setBoolPref: function setBoolPref(aPrefName, aValue) {
    this._setOne(aPrefName, aValue, "bool");
  },

  setCharPref: function setCharPref(aPrefName, aValue) {
    this._setOne(aPrefName, aValue, "string");
  },

  setIntPref: function setIntPref(aPrefName, aValue) {
    this._setOne(aPrefName, aValue, "int");
  },

  _get: function _get(prefs) {
    let values = sendMessageToJava({
      type: "SharedPreferences:Get",
      preferences: prefs,
      branch: this._branch,
    });
    return JSON.parse(values);
  },

  _getOne: function _getOne(aPrefName, aType) {
    let prefs = [];
    prefs.push({
      name: aPrefName,
      type: aType,
    });
    let values = this._get(prefs);
    if (values.length != 1) {
      throw new Error("Got too many values: " + values.length);
    }
    return values[0].value;
  },

  getBoolPref: function getBoolPref(aPrefName) {
    return this._getOne(aPrefName, "bool");
  },

  getCharPref: function getCharPref(aPrefName) {
    return this._getOne(aPrefName, "string");
  },

  getIntPref: function getIntPref(aPrefName) {
    return this._getOne(aPrefName, "int");
  },

  /**
   * Invoke aObserver after a change to the preference aDomain in the
   * current branch.
   */
  addObserver: function addObserver(aDomain, aObserver, aHoldWeak) {
    if (!aDomain)
      throw new Error("aDomain must not be null");
    if (!aObserver)
      throw new Error("aObserver must not be null");
    if (aHoldWeak)
      throw new Error("Weak references not yet implemented.");

    if (!this._observers.hasOwnProperty(aDomain))
      this._observers[aDomain] = [];
    if (this._observers[aDomain].indexOf(aObserver) > -1)
      return;

    this._observers[aDomain].push(aObserver);

    this._updateAndroidListener();
  },

  /**
   * Do not invoke aObserver after a change to the preference aDomain
   * in the current branch.
   */
  removeObserver: function removeObserver(aDomain, aObserver) {
    if (!this._observers.hasOwnProperty(aDomain))
      return;
    let index = this._observers[aDomain].indexOf(aObserver);
    if (index < 0)
      return;

    this._observers[aDomain].splice(index, 1);
    if (this._observers[aDomain].length < 1)
      delete this._observers[aDomain];

    this._updateAndroidListener();
  },

  _updateAndroidListener: function _updateAndroidListener() {
    if (this._listening && Object.keys(this._observers).length < 1)
      this._uninstallAndroidListener();
    if (!this._listening && Object.keys(this._observers).length > 0)
      this._installAndroidListener();
  },

  _installAndroidListener: function _installAndroidListener() {
    if (this._listening)
      return;
    this._listening = true;

    Services.obs.addObserver(this, "SharedPreferences:Changed", false);
    sendMessageToJava({
      type: "SharedPreferences:Observe",
      enable: true,
      branch: this._branch,
    });
  },

  observe: function observe(aSubject, aTopic, aData) {
    if (aTopic != "SharedPreferences:Changed") {
      return;
    }

    let msg = JSON.parse(aData);
    if (msg.branch != this._branch) {
      return;
    }

    if (!this._observers.hasOwnProperty(msg.key)) {
      return;
    }

    let observers = this._observers[msg.key];
    for (let obs of observers) {
      obs.observe(obs, msg.key, msg.value);
    }
  },

  _uninstallAndroidListener: function _uninstallAndroidListener() {
    if (!this._listening)
      return;
    this._listening = false;

    Services.obs.removeObserver(this, "SharedPreferences:Changed");
    sendMessageToJava({
      type: "SharedPreferences:Observe",
      enable: false,
      branch: this._branch,
    });
  },
};
