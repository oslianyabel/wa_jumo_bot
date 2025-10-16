import asyncio
import json
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_postgres_connection():
    """Establishes a connection to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
        )
        return conn
    except psycopg2.Error as e:
        # It's better to return the error than a string
        # to handle it more effectively in the calling function.
        return e


async def async_execute_query(input_query: str):
    return execute_query(input_query)


def execute_query(input_query: str):
    """
    Executes a read-only SQL query on a PostgreSQL database.

    Args:
        input_query (str): A raw SQL query string (e.g., 'SELECT COUNT(*) FROM users;').
        Only SELECT statements are allowed.

    Returns:
        str: A JSON string containing the query results or an error message.
    """
    if not input_query.strip().upper().startswith("SELECT"):
        return json.dumps(
            {
                "status": "error",
                "message": "Operation not allowed. Only read-only queries (SELECT) are permitted.",
            }
        )

    conn = None
    try:
        conn = get_postgres_connection()

        if isinstance(conn, Exception):
            return json.dumps(
                {"status": "error", "message": f"Database connection error: {conn}"}
            )

        with conn.cursor() as cur:
            cur.execute(input_query)

            if not cur.description:
                return json.dumps(
                    {
                        "status": "success",
                        "results": [],
                        "row_count": 0,
                        "message": "Query executed successfully, but it did not return any data.",
                    }
                )

            columns = [desc[0] for desc in cur.description]
            results = cur.fetchall()

            formatted_results = [dict(zip(columns, row)) for row in results]

            return json.dumps(
                {
                    "status": "success",
                    "results": formatted_results,
                    "row_count": len(formatted_results),
                }
            )

    except psycopg2.Error as e:
        return json.dumps({"status": "error", "message": f"Query execution error: {e}"})

    except Exception as e:
        return json.dumps(
            {"status": "error", "message": f"An unexpected error occurred: {e}"}
        )

    finally:
        if conn and not isinstance(conn, Exception):
            conn.close()


if __name__ == "__main__":

    async def main():
        result = await async_execute_query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"
        )
        print(result)

    asyncio.run(main())
