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
            console.error("Missing BACKEND_URL or SCHEDULER_SHARED_SECRET environment variables.");
            return;
        }

        try {
            console.log(`Firing scheduled run to ${targetUrl}...`);

            const response = await fetch(targetUrl, {
                method: "POST",
                headers: {
                    "X-Scheduler-Secret": secret,
                    "Content-Type": "application/json"
                }
            });

            const status = response.status;
            const text = await response.text();

            if (response.ok) {
                console.log(`Success [${status}]:`, text);
            } else {
                console.error(`Failed [${status}]:`, text);
            }
        } catch (error) {
            // Do not throw the error to avoid the worker retrying the same invocation.
            // Simply log and exit cleanly.
            console.error("Error during scheduled fetch:", error);
        }
    },
};
