// Full screen without the system bars: the navigation bar (recents, home, back) sat beside the on-screen A / B / R buttons, so a thumb on them could open recents
// and swipe the game away. The bars come back for a moment with a swipe from the edge. Called from the native front end (app/jni/android_main.c) each time the
// game window gains focus, since dialogs (the name entry) and returning from another app bring the bars back.
package com.nxnative;

import android.app.Activity;
import android.os.Build;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;

public final class Immersive {
    private static final class Api30 {
        static void apply(Window w) {
            w.setDecorFitsSystemWindows(false);
            WindowInsetsController c = w.getInsetsController();
            if (c == null) return;
            c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            c.hide(WindowInsets.Type.systemBars());
        }
    }

    @SuppressWarnings("deprecation")
    private static void applyLegacy(Window w) {
        w.getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
    }

    public static void apply(final Activity a) {
        a.runOnUiThread(new Runnable() {
            public void run() {
                Window w = a.getWindow();
                if (Build.VERSION.SDK_INT >= 30) Api30.apply(w);
                else applyLegacy(w);
            }
        });
    }
}
