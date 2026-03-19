defmodule PodqapathWeb.Router do
  use PodqapathWeb, :router

  pipeline :api do
    plug PodqapathWeb.Plugs.Cors
    plug :accepts, ["json"]
  end

  scope "/api", PodqapathWeb do
    pipe_through :api

    # Preflight handler for all /api/* routes
    options "/*path", ApiController, :options

    get  "/health",    ApiController, :health
    post "/filters",   ApiController, :filters
    post "/tickets",   ApiController, :tickets
    post "/pr-diff",   ApiController, :pr_diff
    post "/chat",      ApiController, :chat
    post "/run-tests", ApiController, :run_tests
  end

  # Enable LiveDashboard in development
  if Application.compile_env(:podqapath, :dev_routes) do
    import Phoenix.LiveDashboard.Router

    scope "/dev" do
      pipe_through [:fetch_session, :protect_from_forgery]

      live_dashboard "/dashboard", metrics: PodqapathWeb.Telemetry
    end
  end
end
