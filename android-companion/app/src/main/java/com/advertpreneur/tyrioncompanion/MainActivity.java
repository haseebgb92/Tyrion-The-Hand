package com.advertpreneur.tyrioncompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Build;
import android.content.Intent;
import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.text.InputType;

import org.json.JSONObject;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public class MainActivity extends Activity {
    private static final String SERVER = "https://haseeb-optiplex-3050.tailb87e57.ts.net:8443";
    private static final String KEY_ALIAS = "tyrion_companion_device_v1";
    private static final int RED = Color.rgb(116, 41, 54);
    private static final int GOLD = Color.rgb(177, 135, 78);
    private static final int INK = Color.rgb(61, 45, 48);
    private static final int BG = Color.rgb(250, 248, 244);
    private FrameLayout screen;
    private EditText codeInput;
    private TextView feedback;
    private Button pairButton;
    private WebView workspace;
    private String deviceToken = null;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(Color.rgb(255,253,250));
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR |
                View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        screen = new FrameLayout(this);
        screen.setBackgroundColor(BG);
        setContentView(screen);
        deviceToken = loadSecret();
        if (deviceToken != null && !deviceToken.isEmpty()) openWorkspace();
        else showPairing(null);
        inspectDeepLink(getIntent());
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        inspectDeepLink(intent);
    }

    private void inspectDeepLink(Intent intent) {
        Uri u=intent == null ? null : intent.getData();
        if(u == null || !"tyrioncompanion".equals(u.getScheme()) || !"pair".equals(u.getHost()))return;
        String server=u.getQueryParameter("server");
        String code=u.getQueryParameter("code");
        if(!SERVER.equals(server) || code==null || !code.matches("[0-9]{8}")) {
            showPairing("The QR code does not match this Tyrion PC.");
            return;
        }
        showPairing(null);
        codeInput.setText(code);
        pairWithPc();
    }

    private GradientDrawable shape(int color,int radius){
        GradientDrawable d=new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radius));
        return d;
    }
    private int dp(float amount){return Math.round(amount*getResources().getDisplayMetrics().density);}
    private TextView text(String s,int size,int color,boolean bold){
        TextView t=new TextView(this);
        t.setText(s);
        t.setTextSize(size);
        t.setTextColor(color);
        t.setLineSpacing(dp(2),1f);
        if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return t;
    }
    private LinearLayout.LayoutParams block(int top,int bottom){
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(0,dp(top),0,dp(bottom));
        return p;
    }
    private void showPairing(String error){
        if(workspace!=null){workspace.destroy();workspace=null;}
        screen.removeAllViews();
        ScrollView scroll=new ScrollView(this);
        scroll.setFillViewport(true);
        screen.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(23),dp(29),dp(23),dp(23));
        scroll.addView(root,new ScrollView.LayoutParams(-1,-1));

        ImageView seal=new ImageView(this);
        seal.setImageResource(R.drawable.tyrion_seal);
        seal.setScaleType(ImageView.ScaleType.FIT_CENTER);
        LinearLayout.LayoutParams img=new LinearLayout.LayoutParams(dp(83),dp(83));
        img.gravity=Gravity.CENTER_HORIZONTAL;img.bottomMargin=dp(13);
        root.addView(seal,img);

        TextView name=text("Tyrion",36,RED,true);
        name.setTypeface(Typeface.create("serif",Typeface.BOLD));
        name.setGravity(Gravity.CENTER);
        root.addView(name);
        TextView subtitle=text("THE COMPANION",11,GOLD,true);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setLetterSpacing(.26f);
        root.addView(subtitle,block(0,18));
        TextView description=text("One steady hand. Wherever you are.",14,INK,false);
        description.setGravity(Gravity.CENTER);
        root.addView(description,block(0,28));

        LinearLayout card=new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(21),dp(22),dp(21),dp(22));
        card.setBackground(shape(Color.WHITE,16));
        root.addView(card,block(0,12));
        TextView heading=text("Connect to your PC",22,RED,true);
        heading.setTypeface(Typeface.create("serif",Typeface.BOLD));
        card.addView(heading);
        TextView guide=text("On your computer, open Tyrion → Connections → Pair Android phone. Scan the QR code or enter its 8-digit code below.",13,Color.rgb(120,108,103),false);
        card.addView(guide,block(9,15));
        TextView codeLabel=text("PAIRING CODE",10,GOLD,true);
        codeLabel.setLetterSpacing(.15f);
        card.addView(codeLabel,block(0,5));
        codeInput=new EditText(this);
        codeInput.setSingleLine(true);
        codeInput.setTextSize(25);
        codeInput.setTextColor(INK);
        codeInput.setLetterSpacing(.20f);
        codeInput.setHint("00000000");
        codeInput.setGravity(Gravity.CENTER);
        codeInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        codeInput.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(8)});
        codeInput.setBackground(shape(Color.rgb(248,245,240),9));
        codeInput.setPadding(dp(12),dp(11),dp(12),dp(11));
        card.addView(codeInput,block(0,13));
        pairButton=new Button(this);
        pairButton.setText("PAIR WITH TYRION");
        pairButton.setTextColor(Color.WHITE);
        pairButton.setAllCaps(false);
        pairButton.setBackground(shape(RED,10));
        card.addView(pairButton,new LinearLayout.LayoutParams(-1,dp(49)));
        pairButton.setOnClickListener(v->pairWithPc());
        feedback=text(error==null?"Your PC and phone must both be connected to Tailscale.":error,12,
                     error==null?Color.rgb(130,115,106):RED,false);
        feedback.setGravity(Gravity.CENTER);
        card.addView(feedback,block(14,0));
        Button tailscale=new Button(this);
        tailscale.setText("Open Tailscale");
        tailscale.setTextColor(RED);
        tailscale.setAllCaps(false);
        tailscale.setBackground(shape(Color.rgb(243,235,226),10));
        root.addView(tailscale,block(16,7));
        tailscale.setOnClickListener(v->{
            try{Intent launch=getPackageManager().getLaunchIntentForPackage("com.tailscale.ipn");
                if(launch!=null)startActivity(launch);
                else startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://tailscale.com/download/android")));
            }catch(Exception ignored){}
        });
        TextView note=text("Your data stays on the PC. All projects, schedules, tasks and updates are relayed live through your private tailnet.",12,Color.rgb(129,117,112),false);
        note.setGravity(Gravity.CENTER);
        root.addView(note,block(10,12));
    }

    private void pairWithPc(){
        String code=codeInput.getText().toString().trim();
        if(!code.matches("[0-9]{8}")){feedback.setText("Enter the eight-digit code displayed on your PC.");return;}
        pairButton.setEnabled(false);
        feedback.setText("Connecting securely to your PC…");
        new Thread(()->{
            try{
                JSONObject payload=new JSONObject();
                payload.put("code",code);
                payload.put("name",Build.MANUFACTURER+" "+Build.MODEL);
                JSONObject response=request("POST",SERVER+"/api/mobile/pair",payload,null);
                String token=response.getString("token");
                saveSecret(token);
                deviceToken=token;
                runOnUiThread(this::openWorkspace);
            }catch(Exception error){
                runOnUiThread(()->{
                    pairButton.setEnabled(true);
                    feedback.setText("Pairing failed: "+sanitize(error.getMessage())+
                          "\nCheck Tailscale and generate a fresh code on the PC.");
                });
            }
        },"tyrion-pair").start();
    }

    private JSONObject request(String method,String url,JSONObject body,String token) throws Exception{
        HttpsURLConnection c=(HttpsURLConnection)new URL(url).openConnection();
        c.setRequestMethod(method);c.setConnectTimeout(9000);c.setReadTimeout(10000);
        c.setRequestProperty("Accept","application/json");
        c.setUseCaches(false);c.setInstanceFollowRedirects(false);
        if(token!=null)c.setRequestProperty("X-Tyrion-Device",token);
        if(body!=null){
            byte[] b=body.toString().getBytes(StandardCharsets.UTF_8);
            c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");
            try(OutputStream out=c.getOutputStream()){out.write(b);}
        }
        int code=c.getResponseCode();
        InputStream stream=code>=200&&code<300?c.getInputStream():c.getErrorStream();
        ByteArrayOutputStream buffer=new ByteArrayOutputStream();
        if(stream!=null){
            byte[] chunk=new byte[4096];
            int count,total=0;
            while((count=stream.read(chunk))!=-1 && total<16384){
                int allowed=Math.min(count,16384-total);
                buffer.write(chunk,0,allowed);total+=allowed;
            }
            stream.close();
        }
        byte[] bytes=buffer.toByteArray();
        c.disconnect();
        JSONObject data=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
        if(code<200||code>=300)throw new Exception(data.optString("error","HTTP "+code));
        return data;
    }

    private void openWorkspace(){
        screen.removeAllViews();
        getWindow().setStatusBarColor(Color.rgb(255,252,249));
        workspace=new WebView(this);
        workspace.setBackgroundColor(BG);
        workspace.getSettings().setJavaScriptEnabled(true);
        workspace.getSettings().setDomStorageEnabled(true);
        workspace.getSettings().setAllowFileAccess(false);
        workspace.getSettings().setAllowContentAccess(false);
        workspace.getSettings().setAllowFileAccessFromFileURLs(false);
        workspace.getSettings().setAllowUniversalAccessFromFileURLs(false);
        workspace.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        workspace.getSettings().setSafeBrowsingEnabled(true);
        workspace.getSettings().setSupportZoom(false);
        workspace.setWebChromeClient(new WebChromeClient());
        workspace.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri u=request.getUrl();
                if("https".equals(u.getScheme()) &&
                   "haseeb-optiplex-3050.tailb87e57.ts.net".equals(u.getHost()) && u.getPort()==8443)
                    return false;
                if("http".equals(u.getScheme())||"https".equals(u.getScheme())){
                    try{startActivity(new Intent(Intent.ACTION_VIEW,u));}catch(Exception ignored){}
                }
                return true;
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest req,WebResourceError error){
                if(req.isForMainFrame())runOnUiThread(()->showOffline("PC connection unavailable. Make sure Tailscale is connected."));
            }
            @Override public void onReceivedHttpError(WebView view,WebResourceRequest req,android.webkit.WebResourceResponse response){
                if(!req.isForMainFrame())return;
                if(response.getStatusCode()==401){clearSecret();runOnUiThread(()->showPairing("This device was disconnected from the PC. Please pair again."));}
                else if(response.getStatusCode()>=500)runOnUiThread(()->showOffline("PC responded with an error. Retry after checking Tyrion."));
            }
        });
        workspace.setOnLongClickListener(v->{
            new AlertDialog.Builder(this).setTitle("Tyrion – The Companion")
             .setItems(new String[]{"Refresh live workspace","Disconnect this device","Cancel"},
               (dialog,which)->{if(which==0)workspace.reload();
                   else if(which==1)new AlertDialog.Builder(this).setTitle("Disconnect?")
                     .setMessage("Forget this phone's current Tyrion pairing? You can pair again from the PC.")
                     .setPositiveButton("Disconnect",(d,w)->{clearSecret();showPairing(null);})
                     .setNegativeButton("Cancel",null).show();})
             .show();
            return true;
        });
        screen.addView(workspace,new FrameLayout.LayoutParams(-1,-1));
        CookieManager manager=CookieManager.getInstance();
        manager.setAcceptCookie(true);
        manager.setAcceptThirdPartyCookies(workspace,false);
        manager.setCookie(SERVER,"tyrion_device="+deviceToken+"; Path=/; Secure; HttpOnly; SameSite=Strict",
                         value->{manager.flush();workspace.loadUrl(SERVER+"/");});
    }

    private void showOffline(String reason){
        if(workspace!=null){workspace.destroy();workspace=null;}
        screen.removeAllViews();
        LinearLayout panel=new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(30),dp(75),dp(30),dp(25));
        panel.setGravity(Gravity.CENTER_HORIZONTAL);
        screen.addView(panel,new FrameLayout.LayoutParams(-1,-1));
        TextView heading=text("PC connection unavailable",25,RED,true);
        heading.setTypeface(Typeface.create("serif",Typeface.BOLD));
        panel.addView(heading,block(0,14));
        TextView details=text(reason+"\n\nTyrion continues running on the PC. No local data has been changed.",14,INK,false);
        details.setGravity(Gravity.CENTER);
        panel.addView(details,block(5,18));
        Button retry=new Button(this);
        retry.setText("Retry connection");
        retry.setTextColor(Color.WHITE);retry.setBackground(shape(RED,10));
        panel.addView(retry,new LinearLayout.LayoutParams(-1,dp(48)));
        retry.setOnClickListener(v->openWorkspace());
        Button unplug=new Button(this);
        unplug.setText("Pair again");
        panel.addView(unplug,block(9,0));
        unplug.setOnClickListener(v->showPairing(null));
    }

    private String sanitize(String text){
        if(text==null)return "PC offline";
        return text.replaceAll("[\\n\\r]"," ").substring(0,Math.min(160,text.length()));
    }
    private void saveSecret(String value) throws Exception{
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(!store.containsAlias(KEY_ALIAS)){
            KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                 KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                 .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                 .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            generator.generateKey();
        }
        SecretKey key=(SecretKey)store.getKey(KEY_ALIAS,null);
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,key);
        String encoded=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+"."+
                Base64.encodeToString(cipher.doFinal(value.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP);
        getPreferences(MODE_PRIVATE).edit().putString("session",encoded).apply();
    }
    private String loadSecret(){
        try{
            String value=getPreferences(MODE_PRIVATE).getString("session",null);
            if(value==null)return null;
            String[] parts=value.split("\\.");
            if(parts.length!=2)return null;
            KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
            SecretKey key=(SecretKey)store.getKey(KEY_ALIAS,null);
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,Base64.decode(parts[0],Base64.DEFAULT)));
            return new String(cipher.doFinal(Base64.decode(parts[1],Base64.DEFAULT)),StandardCharsets.UTF_8);
        }catch(Exception ex){return null;}
    }
    private void clearSecret(){
        deviceToken=null;
        getPreferences(MODE_PRIVATE).edit().clear().apply();
        CookieManager.getInstance().removeAllCookies(null);
        CookieManager.getInstance().flush();
    }
    @Override public void onBackPressed(){
        if(workspace!=null&&workspace.canGoBack())workspace.goBack();
        else if(workspace!=null)new AlertDialog.Builder(this).setTitle("Close Tyrion?")
          .setMessage("Tyrion keeps running on your PC.").setPositiveButton("Close",(d,w)->finish())
          .setNegativeButton("Stay",null).show();
        else super.onBackPressed();
    }
}
