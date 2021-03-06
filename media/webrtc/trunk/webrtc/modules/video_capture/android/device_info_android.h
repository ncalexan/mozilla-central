/*
 *  Copyright (c) 2012 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef WEBRTC_MODULES_VIDEO_CAPTURE_MAIN_SOURCE_ANDROID_DEVICE_INFO_ANDROID_H_
#define WEBRTC_MODULES_VIDEO_CAPTURE_MAIN_SOURCE_ANDROID_DEVICE_INFO_ANDROID_H_

#include <jni.h>
#include "../video_capture_impl.h"
#include "../device_info_impl.h"

#define AndroidJavaCaptureDeviceInfoClass "org/webrtc/videoengine/VideoCaptureDeviceInfoAndroid"
#define AndroidJavaCaptureCapabilityClass "org/webrtc/videoengine/CaptureCapabilityAndroid"

namespace webrtc
{
namespace videocapturemodule
{

// Android logging, uncomment to print trace to
// logcat instead of trace file/callback
// #include <android/log.h>
// #define WEBRTC_TRACE(a,b,c,...)
// __android_log_print(ANDROID_LOG_DEBUG, "*WEBRTCN*", __VA_ARGS__)

class DeviceInfoAndroid : public DeviceInfoImpl {

 public:
  DeviceInfoAndroid(const WebRtc_Word32 id);
  WebRtc_Word32 Init();
  virtual ~DeviceInfoAndroid();
  virtual WebRtc_UWord32 NumberOfDevices();
  virtual WebRtc_Word32 GetDeviceName(
      WebRtc_UWord32 deviceNumber,
      char* deviceNameUTF8,
      WebRtc_UWord32 deviceNameLength,
      char* deviceUniqueIdUTF8,
      WebRtc_UWord32 deviceUniqueIdUTF8Length,
      char* productUniqueIdUTF8 = 0,
      WebRtc_UWord32 productUniqueIdUTF8Length = 0);
  virtual WebRtc_Word32 CreateCapabilityMap(const char* deviceUniqueIdUTF8);

  virtual WebRtc_Word32 DisplayCaptureSettingsDialogBox(
      const char* /*deviceUniqueIdUTF8*/,
      const char* /*dialogTitleUTF8*/,
      void* /*parentWindow*/,
      WebRtc_UWord32 /*positionX*/,
      WebRtc_UWord32 /*positionY*/) { return -1; }
  virtual WebRtc_Word32 GetOrientation(const char* deviceUniqueIdUTF8,
                                       VideoCaptureRotation& orientation);
 private:
  bool IsDeviceNameMatches(const char* name, const char* deviceUniqueIdUTF8);
  enum {_expectedCaptureDelay = 190};
};

}  // namespace videocapturemodule
}  // namespace webrtc

#endif // WEBRTC_MODULES_VIDEO_CAPTURE_MAIN_SOURCE_ANDROID_DEVICE_INFO_ANDROID_H_
