import okhttp3.mockwebserver.MockWebServer;

public final class MockWebServerConstructorProbe {
  public static void main(String[] args) {
    MockWebServer server = null;
    try {
      server = new MockWebServer();
      server.start();
      System.out.println("SETUP=PASS");
    } catch (Throwable failure) {
      System.out.println("SETUP=" + failure);
    } finally {
      try {
        server.shutdown();
        System.out.println("CLEANUP=PASS");
      } catch (Throwable failure) {
        System.out.println("CLEANUP=" + failure);
      }
    }
  }
}
