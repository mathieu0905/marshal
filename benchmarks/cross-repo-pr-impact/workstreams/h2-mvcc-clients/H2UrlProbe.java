import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

public final class H2UrlProbe {
    private H2UrlProbe() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException("usage: H2UrlProbe <jdbc-url> <pass|fail>");
        }

        String url = args[0];
        String expected = args[1];
        String observed = "pass";
        String errorClass = null;
        String errorMessage = null;
        String sqlState = null;
        int errorCode = 0;

        Class.forName("org.h2.Driver");
        try (Connection ignored = DriverManager.getConnection(url, "sa", "")) {
            // Opening the connection is the behavior under test.
        } catch (SQLException error) {
            observed = "fail";
            errorClass = error.getClass().getName();
            errorMessage = error.getMessage();
            sqlState = error.getSQLState();
            errorCode = error.getErrorCode();
        }

        System.out.println("{");
        System.out.println("  \"jdbc_url\": \"" + json(url) + "\",");
        System.out.println("  \"expected\": \"" + expected + "\",");
        System.out.println("  \"observed\": \"" + observed + "\",");
        System.out.println("  \"error_class\": " + nullable(errorClass) + ",");
        System.out.println("  \"error_message\": " + nullable(errorMessage) + ",");
        System.out.println("  \"sql_state\": " + nullable(sqlState) + ",");
        System.out.println("  \"error_code\": " + errorCode + ",");
        System.out.println("  \"result\": \"" + (expected.equals(observed) ? "pass" : "fail") + "\"");
        System.out.println("}");

        if (!expected.equals(observed)) {
            System.exit(1);
        }
    }

    private static String nullable(String value) {
        return value == null ? "null" : "\"" + json(value) + "\"";
    }

    private static String json(String value) {
        return value.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\r", "\\r")
                .replace("\n", "\\n");
    }
}
