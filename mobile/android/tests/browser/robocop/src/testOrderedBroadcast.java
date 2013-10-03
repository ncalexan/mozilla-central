package org.mozilla.gecko.robocop.tests;

import org.mozilla.gecko.robocop.*;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import android.app.Activity;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;

import android.util.Log;


public class testOrderedBroadcast extends JavascriptTest {
    protected BroadcastReceiver mReceiver;

    public testOrderedBroadcast() {
        super("testOrderedBroadcast.js");
    }

    @Override
    public void setUp() throws Exception {
        super.setUp();

        mAsserter.dumpLog("Registering org.mozilla.gecko.test.receiver broadcast receiver");

        IntentFilter filter = new IntentFilter();
        filter.addAction("org.mozilla.gecko.test.receiver");

        mReceiver = new BroadcastReceiver() {
                @Override
                public void onReceive(Context context, Intent intent) {
                    try {
                        JSONObject o = new JSONObject();
                        o.put("c", "efg");
                        o.put("d", 456);
                        // Feed the received token back to the sender.
                        o.put("token", intent.getStringExtra("token"));
                        String data = o.toString();

                        setResultCode(Activity.RESULT_OK);
                        setResultData(data);
                    } catch (JSONException e) {
                        setResultCode(Activity.RESULT_CANCELED);
                        setResultData(null);
                    }
                }
            };

        // We must register the receiver in a Fennec context to avoid a
        // SecurityException.
        getActivity().getApplicationContext().registerReceiver(mReceiver, filter);
    }

    @Override
    public void tearDown() throws Exception {
        super.tearDown();

        mAsserter.dumpLog("Unregistering org.mozilla.gecko.test.receiver broadcast receiver");

        if (mReceiver != null) {
            getActivity().getApplicationContext().unregisterReceiver(mReceiver);
            mReceiver = null;
        }
    }
}
