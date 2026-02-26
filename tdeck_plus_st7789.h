#pragma once

#include "esphome/core/component.h"
#include "esphome/components/display/display_buffer.h"
#include "esphome/components/spi/spi.h"

namespace esphome {
namespace tdeck_plus_st7789 {

class TDeckPlusST7789 : public PollingComponent,
                         public display::DisplayBuffer,
                         public spi::SPIDevice<spi::BIT_ORDER_MSB_FIRST, spi::CLOCK_POLARITY_LOW,
                                               spi::CLOCK_PHASE_LEADING, spi::DATA_RATE_20MHZ> {
 public:
  void setup() override;
  void dump_config() override;
  void update() override;
  
  void set_dc_pin(GPIOPin *dc_pin) { dc_pin_ = dc_pin; }
  void set_reset_pin(GPIOPin *reset_pin) { reset_pin_ = reset_pin; }
  void set_backlight_pin(GPIOPin *backlight_pin) { backlight_pin_ = backlight_pin; }

  display::DisplayType get_display_type() override { return display::DisplayType::DISPLAY_TYPE_COLOR; }

 protected:
  void draw_absolute_pixel_internal(int x, int y, Color color) override;
  void init_reset_();
  void write_command_(uint8_t cmd);
  void write_data_(uint8_t data);
  void set_addr_window_(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2);
  
  int get_height_internal() override { return 240; }
  int get_width_internal() override { return 320; }

  GPIOPin *dc_pin_{nullptr};
  GPIOPin *reset_pin_{nullptr};
  GPIOPin *backlight_pin_{nullptr};
};

}  // namespace tdeck_plus_st7789
}  // namespace esphome
