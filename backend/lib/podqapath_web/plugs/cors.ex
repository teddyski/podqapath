defmodule PodqapathWeb.Plugs.Cors do
  @moduledoc """
  Simple CORS plug that allows requests from the React dev server.
  Handles OPTIONS preflight requests inline.
  """
  import Plug.Conn

  @allowed_origins ["http://localhost:5173", "http://localhost:3000"]

  def init(opts), do: opts

  def call(conn, _opts) do
    origin = conn |> get_req_header("origin") |> List.first() || ""

    conn =
      if origin in @allowed_origins do
        conn
        |> put_resp_header("access-control-allow-origin", origin)
        |> put_resp_header("access-control-allow-methods", "GET, POST, OPTIONS")
        |> put_resp_header("access-control-allow-headers", "content-type, authorization")
        |> put_resp_header("access-control-max-age", "86400")
      else
        conn
      end

    # Handle preflight
    if conn.method == "OPTIONS" do
      conn
      |> send_resp(204, "")
      |> halt()
    else
      conn
    end
  end
end
