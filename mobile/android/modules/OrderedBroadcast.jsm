// -*- Mode: js2; tab-width: 2; indent-tabs-mode: nil; js2-basic-offset: 2; js2-skip-preprocessor-directives: t; -*-
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */
"use strict";

this.EXPORTED_SYMBOLS = ["sendOrderedBroadcast"];

const { classes: Cc, interfaces: Ci, utils: Cu } = Components;

// For adding observers.
Cu.import("resource://gre/modules/Services.jsm");

function sendMessageToJava(aMessage) {
  return Cc["@mozilla.org/android/bridge;1"].getService(Ci.nsIAndroidBridge).
    handleGeckoMessage(JSON.stringify(aMessage));
}

let _callbackId = 1;

/**
 * Send an ordered broadcast to Java.
 *
 * Internally calls Context.sendOrderedBroadcast.
 *
 * aAction {String} should be a string with a qualified name (like
 * org.mozilla.gecko.action) that will be broadcast.
 *
 * aToken {Object} is a piece of arbitrary data that will be given as
 * a parameter to the callback (possibly null).
 *
 * aCallback {function} should accept three arguments: the data
 * returned from Java as an Object; the specified token; and the
 * specified action.
 *
 * aPermission {String} should be a string with an Android permission
 * that packages must have to respond to the ordered broadcast, or
 * null to allow all packages to respond.
 */
function sendOrderedBroadcast(aAction, aToken, aCallback, aPermission) {
  let callbackId = _callbackId++;
  let responseEvent = "OrderedBroadcast:Response:" + callbackId;

  let observer = {
    callbackId: callbackId,
    callback: aCallback,

    observe: function observe(aSubject, aTopic, aData) {
      if (aTopic != responseEvent) {
        return;
      }

      // Unregister observer as soon as possible.
      Services.obs.removeObserver(observer, responseEvent);

      let msg = JSON.parse(aData);
      if (!msg.action || !msg.token || !msg.token.callbackId)
        return;

      let callbackId = msg.token.callbackId;
      let aToken = msg.token.data;
      let aAction = msg.action;
      let aData = msg.data ? JSON.parse(msg.data) : null;

      let aCallback = this.callback;
      if (!aCallback)
        return;

      // This is called from within a notified observer, so we don't
      // need to take special pains to catch exceptions.
      aCallback(aData, aToken, aAction);
    },
  };

  Services.obs.addObserver(observer, responseEvent, false);

  sendMessageToJava({
    type: "OrderedBroadcast:Send",
    action: aAction,
    responseEvent: responseEvent,
    token: { callbackId: callbackId, data: aToken || null },
    permission: aPermission || null,
  });
};
