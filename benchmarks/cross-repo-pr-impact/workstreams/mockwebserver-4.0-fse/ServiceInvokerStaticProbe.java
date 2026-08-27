import okhttp3.HttpUrl;
import okhttp3.MediaType;

public final class ServiceInvokerStaticProbe {
  private static final class ServiceShape {
    static final HttpUrl SERVICE_URL = HttpUrl.parse("https://api.opengamma.com");
    static final MediaType MEDIA_JSON = MediaType.parse("application/json");
  }

  public static void main(String[] args) {
    load("FIRST");
    load("SECOND");
  }

  private static void load(String attempt) {
    try {
      System.out.println(attempt + "=" + ServiceShape.SERVICE_URL + " " + ServiceShape.MEDIA_JSON);
    } catch (Throwable failure) {
      System.out.println(attempt + "=" + failure);
      failure.printStackTrace(System.out);
    }
  }
}
