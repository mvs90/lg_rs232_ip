"""One replaceable, non-persistent view timer; manual actions always take over."""

import asyncio


class TemporaryView:
    def _init_temporary_view(self):
        self._view_generation = 0
        self._view_timer = None
        self._view_lease = None
        self._view_pending_previous = None

    def _cancel_temporary_view(self):
        self._view_generation += 1
        self._view_lease = None
        self._view_pending_previous = None
        if self._view_timer:
            self._view_timer.cancel()
            self._view_timer = None

    def _schedule_view_return(
        self, app, previous, view, duration, transition, generation
    ):
        if generation != self._view_generation or self._ha_stopping:
            return
        self._view_pending_previous = None
        lease = self._view_lease = dict(
            previous=previous,
            view=view,
            input=app.selected_input,
            transition=transition,
            generation=generation,
        )

        def expire():
            self._view_timer = None
            self.hass.async_create_task(self._async_return_view(app, lease))

        self._view_timer = asyncio.get_running_loop().call_later(duration, expire)

    async def _async_return_view(self, app, lease):
        async with self._control_lock:
            if self._view_lease is not lease:
                return
            self._view_lease = None
            if (
                self._ha_stopping
                or self.external_owner
                or self.presentation_active
                or not app.resident_connected
                or self.power is not True
                or (app.selected_view or "hdmi_full") != lease["view"]
                or app.selected_input != lease["input"]
            ):
                return
            view, input_id = lease["previous"]
            try:
                if view == "hdmi_full":
                    if not await app.async_select_hdmi(
                        input_id, transition=lease["transition"]
                    ):
                        return
                    self._current_input_id = input_id
                    self._source = self._resolve_source_name(input_id)
                elif view in self.app_view_sources:
                    await app.async_select_view(view, transition=lease["transition"])
                    self._source = self.app_view_sources[view]
                self.async_write_ha_state()
            except Exception:
                self._presentation_error = (
                    "Temporary view could not restore the previous view"
                )
                self.async_write_ha_state()
