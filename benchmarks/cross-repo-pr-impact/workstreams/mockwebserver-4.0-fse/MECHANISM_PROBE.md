# MockWebServer 4.0.0 mechanism probes

The probes separate the two classpath-skew mechanisms without selecting or modifying a client revision.

`MockWebServerConstructorProbe` uses the setup and unconditional cleanup shape in jsonapi-converter. An aligned MockWebServer 4.0.0, OkHttp 4.0.0 and Okio 2.2.2 classpath starts and shuts down. Replacing OkHttp and Okio with the Retrofit 2.5-era 3.12.0 and 1.15.0 binaries produces:

```text
SETUP=java.lang.NoSuchMethodError: 'java.util.List okhttp3.internal.Util.immutableListOf(java.lang.Object[])'
CLEANUP=java.lang.NullPointerException
```

`ServiceInvokerStaticProbe` uses the three static OkHttp values initialized by JavaSDK's `ServiceInvoker`. OkHttp 4.0.0 with Okio 2.2.2 initializes twice. With JavaSDK's pinned Okio 1.17.5, the first access fails in `okhttp3.internal.Util.<clinit>` because `okio.Options.Companion` is absent, and the second access reports:

```text
java.lang.NoClassDefFoundError: Could not initialize class ServiceInvokerStaticProbe$ServiceShape
```

Run `./run_mechanism_probes.sh` from this directory. Downloads and compiled classes stay under `.work/mockwebserver-4.0-fse/probe-run`; the four logs are written to the corresponding results directory. These are source/dependency mechanism probes, not client A0/A1/A2 arms.
