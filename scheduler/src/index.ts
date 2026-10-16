/**
 * A minimal Cloudflare Worker trigger.
 * Its sole responsibility is to fire on a cron schedule and call the internal backend endpoint.
 */

export interface Env {
    BACKEND_URL: string;
    SCHEDULER_SHARED_SECRET: string;
}

export default {
    async scheduled(
        controller: ScheduledController,
        env: Env,
        ctx: ExecutionContext
    ): Promise<void> {
        const targetUrl = env.BACKEND_URL;
        const secret = env.SCHEDULER_SHARED_SECRET;

        if (!targetUrl || !secret) {
            throw new Error("Missing required scheduler configuration.");
        }

        const target = new URL(targetUrl);
        if (target.pathname !== "/api/v1/internal/scheduled-monitoring/run") {
            throw new Error("BACKEND_URL must target the scheduled-monitoring endpoint.");
        }

        const response = await fetch(target, {
            method: "POST",
            headers: {
                "X-Scheduler-Secret": secret,
                "Content-Type": "application/json"
            }
        });
        if (!response.ok) {
            throw new Error(`Scheduled backend returned HTTP ${response.status}.`);
        }

        console.info(`Scheduled monitoring completed with HTTP ${response.status}.`);
    },
};
