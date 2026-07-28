import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/scheduler.dart';

/// Dio interceptor that periodically pumps the UI event loop during long requests.
/// This prevents Windows from marking the app as "not responding" during VLM
/// operations that can take 2-3 minutes.
class UiKeepAliveInterceptor extends Interceptor {
  Timer? _keepAliveTimer;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    // Start pumping events every 100ms during the request
    _keepAliveTimer?.cancel();
    _keepAliveTimer = Timer.periodic(
      const Duration(milliseconds: 100),
      (_) {
        // Force the UI to process pending events
        SchedulerBinding.instance.scheduleFrame();
      },
    );
    handler.next(options);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    _keepAliveTimer?.cancel();
    _keepAliveTimer = null;
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    _keepAliveTimer?.cancel();
    _keepAliveTimer = null;
    handler.next(err);
  }
}
