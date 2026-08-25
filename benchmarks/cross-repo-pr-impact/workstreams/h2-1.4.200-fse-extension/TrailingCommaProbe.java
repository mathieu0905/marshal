import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;

public final class TrailingCommaProbe {
    private TrailingCommaProbe() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException("usage: TrailingCommaProbe <trailing|fixed> <pass|fail>");
        }
        String sql = args[0].equals("trailing")
                ? "CREATE TABLE T (ID INT, NAME VARCHAR(20),)"
                : "CREATE TABLE T (ID INT, NAME VARCHAR(20))";
        String expected = args[1];
        String observed = "pass";
        String error = null;
        try (Connection connection = DriverManager.getConnection("jdbc:h2:mem:probe", "sa", "");
                Statement statement = connection.createStatement()) {
            statement.execute(sql);
        } catch (SQLException exception) {
            observed = "fail";
            error = exception.getMessage();
        }
        System.out.println("{");
        System.out.println("  \"sql_variant\": \"" + args[0] + "\",");
        System.out.println("  \"expected\": \"" + expected + "\",");
        System.out.println("  \"observed\": \"" + observed + "\",");
        System.out.println("  \"error\": " + (error == null ? "null" : "\"" + json(error) + "\"") + ",");
        System.out.println("  \"result\": \"" + (expected.equals(observed) ? "pass" : "fail") + "\"");
        System.out.println("}");
        if (!expected.equals(observed)) {
            System.exit(1);
        }
    }

    private static String json(String value) {
        return value.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\r", "\\r")
                .replace("\n", "\\n");
    }
}
