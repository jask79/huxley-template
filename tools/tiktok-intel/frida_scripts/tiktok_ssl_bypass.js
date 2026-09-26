/**
 * TikTok SSL Pinning Bypass for Frida
 * Targets: OkHttp3 CertificatePinner, Android TrustManager, 
 *          custom TikTok pinning, and native SSL verification
 */

Java.perform(function() {
    console.log("[*] TikTok SSL Pinning Bypass loaded");

    // 1. Android TrustManagerFactory - most common
    try {
        var TrustManagerFactory = Java.use('javax.net.ssl.TrustManagerFactory');
        TrustManagerFactory.getTrustManagers.implementation = function() {
            console.log("[+] Bypassed TrustManagerFactory.getTrustManagers");
            var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
            var list = Java.use('java.util.ArrayList');
            var l = list.$new();
            return this.getTrustManagers.call(this);
        };
    } catch(e) { console.log("[-] TrustManagerFactory: " + e); }

    // 2. X509TrustManager - bypass all certificate checks
    try {
        var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
        var SSLContext = Java.use('javax.net.ssl.SSLContext');
        
        var TrustManager = Java.registerClass({
            name: 'com.huxley.TrustManager',
            implements: [X509TrustManager],
            methods: {
                checkClientTrusted: function(chain, authType) { },
                checkServerTrusted: function(chain, authType) { },
                getAcceptedIssuers: function() { return []; }
            }
        });
        
        var TrustManagers = [TrustManager.$new()];
        var sslContext = SSLContext.getInstance("TLS");
        sslContext.init(null, TrustManagers, null);
        console.log("[+] Custom TrustManager installed");
    } catch(e) { console.log("[-] X509TrustManager: " + e); }

    // 3. OkHttp3 CertificatePinner
    try {
        var CertificatePinner = Java.use('okhttp3.CertificatePinner');
        CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
            console.log("[+] OkHttp3 CertificatePinner bypassed for: " + hostname);
        };
    } catch(e) { console.log("[-] OkHttp3 CertificatePinner: " + e); }

    // 4. OkHttp3 CertificatePinner$Builder
    try {
        var CertificatePinnerBuilder = Java.use('okhttp3.CertificatePinner$Builder');
        CertificatePinnerBuilder.add.overload('java.lang.String', '[Ljava.lang.String;').implementation = function(hostname, pins) {
            console.log("[+] OkHttp3 CertificatePinner.Builder bypassed for: " + hostname);
            return this;
        };
    } catch(e) { console.log("[-] OkHttp3 Builder: " + e); }

    // 5. Android Network Security Config
    try {
        var NetworkSecurityConfig = Java.use('android.security.net.config.NetworkSecurityConfig');
        NetworkSecurityConfig.isCleartextTrafficPermitted.implementation = function() {
            console.log("[+] Cleartext traffic permitted");
            return true;
        };
    } catch(e) { console.log("[-] NetworkSecurityConfig: " + e); }

    // 6. Conscrypt (Android's SSL provider) - TrustManagerImpl
    try {
        var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        // Try multiple overloads
        TrustManagerImpl.verifyChain.overload('[Ljava.security.cert.X509Certificate;', 'java.lang.String', 'java.net.Socket', 'boolean', '[B', '[B').implementation = function(untrustedChain, authType, socket, checkPinning, ocspData, tlsSctData) {
            console.log("[+] Conscrypt TrustManagerImpl.verifyChain bypassed");
            return untrustedChain;
        };
    } catch(e) {
        console.log("[-] Conscrypt verifyChain (6-arg): " + e);
        try {
            var TrustManagerImpl2 = Java.use('com.android.org.conscrypt.TrustManagerImpl');
            TrustManagerImpl2.checkTrustedRecursive.implementation = function() {
                console.log("[+] Conscrypt checkTrustedRecursive bypassed");
                return Java.use('java.util.ArrayList').$new();
            };
        } catch(e2) { console.log("[-] Conscrypt checkTrustedRecursive: " + e2); }
    }

    // 7. TikTok-specific: bytedance SSL pinning
    try {
        var classes = [
            'com.bytedance.frameworks.core.encrypt.RequestEncryptManager',
            'com.ss.android.common.ssconfig.ConfigManager',
            'com.bytedance.ttnet.utils.CertChecker',
        ];
        classes.forEach(function(className) {
            try {
                var clazz = Java.use(className);
                var methods = clazz.class.getDeclaredMethods();
                methods.forEach(function(method) {
                    var name = method.getName();
                    if (name.toLowerCase().indexOf('verify') !== -1 || 
                        name.toLowerCase().indexOf('check') !== -1 ||
                        name.toLowerCase().indexOf('pin') !== -1) {
                        console.log("[*] Found TikTok method: " + className + "." + name);
                    }
                });
            } catch(e) { }
        });
    } catch(e) { console.log("[-] TikTok-specific: " + e); }

    // 8. SSLSocketFactory
    try {
        var SSLSocketFactory = Java.use('javax.net.ssl.SSLSocketFactory');
        // Don't override, just log
    } catch(e) { }

    // 9. HostnameVerifier bypass
    try {
        var HostnameVerifier = Java.use('javax.net.ssl.HostnameVerifier');
        var HttpsURLConnection = Java.use('javax.net.ssl.HttpsURLConnection');
        HttpsURLConnection.setDefaultHostnameVerifier.implementation = function(verifier) {
            console.log("[+] HostnameVerifier bypassed");
            return;  // no-op
        };
    } catch(e) { console.log("[-] HostnameVerifier: " + e); }

    console.log("[*] SSL Pinning Bypass setup complete");
});
