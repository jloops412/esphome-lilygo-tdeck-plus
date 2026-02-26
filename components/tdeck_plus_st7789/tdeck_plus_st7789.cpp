#include "tdeck_plus_st7789.h"
#include "esphome/core/log.h"
#include "esphome/core/helpers.h"
#include "esphome/core/hal.h"

#ifdef USE_ESP32
#include "driver/gpio.h"
#endif

namespace esphome {
namespace tdeck_plus_st7789 {

static const char *TAG = "tdeck_plus_st7789";

void TDeckPlusST7789::setup() {
  ESP_LOGCONFIG(TAG, "Setting up T-Deck Plus ST7789...");
  
  this->spi_setup();
  
  // Setup GPIO pins directly using ESP32 HAL
  pinMode(this->dc_pin_, OUTPUT);
  digitalWrite(this->dc_pin_, LOW);
  
  if (this->reset_pin_set_) {
    pinMode(this->reset_pin_, OUTPUT);
  }
  
  if (this->backlight_pin_set_) {
    pinMode(this->backlight_pin_, OUTPUT);
    digitalWrite(this->backlight_pin_, HIGH);  // Turn on backlight
  }
  
  this->init_reset_();
  
  // ST7789V init sequence for T-Deck Plus
  this->write_command_(0x11);  // Sleep out
  delay(120);
  
  this->write_command_(0x36);  // Memory Data Access Control
  this->write_data_(0x00);
  
  this->write_command_(0x3A);  // Interface Pixel Format
  this->write_data_(0x55);     // 16-bit color
  
  this->write_command_(0xB2);  // Porch Setting
  this->write_data_(0x0C);
  this->write_data_(0x0C);
  this->write_data_(0x00);
  this->write_data_(0x33);
  this->write_data_(0x33);
  
  this->write_command_(0xB7);  // Gate Control
  this->write_data_(0x35);
  
  this->write_command_(0xBB);  // VCOM Setting
  this->write_data_(0x19);
  
  this->write_command_(0xC0);  // LCM Control
  this->write_data_(0x2C);
  
  this->write_command_(0xC2);  // VDV and VRH Command Enable
  this->write_data_(0x01);
  
  this->write_command_(0xC3);  // VRH Set
  this->write_data_(0x12);
  
  this->write_command_(0xC4);  // VDV Set
  this->write_data_(0x20);
  
  this->write_command_(0xC6);  // Frame Rate Control
  this->write_data_(0x0F);
  
  this->write_command_(0xD0);  // Power Control 1
  this->write_data_(0xA4);
  this->write_data_(0xA1);
  
  this->write_command_(0xE0);  // Positive Voltage Gamma Control
  this->write_data_(0xD0);
  this->write_data_(0x04);
  this->write_data_(0x0D);
  this->write_data_(0x11);
  this->write_data_(0x13);
  this->write_data_(0x2B);
  this->write_data_(0x3F);
  this->write_data_(0x54);
  this->write_data_(0x4C);
  this->write_data_(0x18);
  this->write_data_(0x0D);
  this->write_data_(0x0B);
  this->write_data_(0x1F);
  this->write_data_(0x23);
  
  this->write_command_(0xE1);  // Negative Voltage Gamma Control
  this->write_data_(0xD0);
  this->write_data_(0x04);
  this->write_data_(0x0C);
  this->write_data_(0x11);
  this->write_data_(0x13);
  this->write_data_(0x2C);
  this->write_data_(0x3F);
  this->write_data_(0x44);
  this->write_data_(0x51);
  this->write_data_(0x2F);
  this->write_data_(0x1F);
  this->write_data_(0x1F);
  this->write_data_(0x20);
  this->write_data_(0x23);
  
  this->write_command_(0x21);  // Display Inversion On
  
  this->write_command_(0x29);  // Display on
  delay(120);
  
  ESP_LOGCONFIG(TAG, "T-Deck Plus ST7789 initialization complete");
}

void TDeckPlusST7789::dump_config() {
  ESP_LOGCONFIG(TAG, "T-Deck Plus ST7789:");
  ESP_LOGCONFIG(TAG, "  DC Pin: GPIO%u", this->dc_pin_);
  if (this->reset_pin_set_) {
    ESP_LOGCONFIG(TAG, "  Reset Pin: GPIO%u", this->reset_pin_);
  }
  if (this->backlight_pin_set_) {
    ESP_LOGCONFIG(TAG, "  Backlight Pin: GPIO%u", this->backlight_pin_);
  }
}

void TDeckPlusST7789::update() {
  this->do_update_();
}

void TDeckPlusST7789::init_reset_() {
  if (this->reset_pin_set_) {
    digitalWrite(this->reset_pin_, HIGH);
    delay(1);
    digitalWrite(this->reset_pin_, LOW);
    delay(10);
    digitalWrite(this->reset_pin_, HIGH);
    delay(10);
  }
}

void TDeckPlusST7789::write_command_(uint8_t cmd) {
  digitalWrite(this->dc_pin_, LOW);
  this->enable();
  this->write_byte(cmd);
  this->disable();
}

void TDeckPlusST7789::write_data_(uint8_t data) {
  digitalWrite(this->dc_pin_, HIGH);
  this->enable();
  this->write_byte(data);
  this->disable();
}

void TDeckPlusST7789::set_addr_window_(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2) {
  this->write_command_(0x2A);  // Column Address Set
  this->write_data_(x1 >> 8);
  this->write_data_(x1 & 0xFF);
  this->write_data_(x2 >> 8);
  this->write_data_(x2 & 0xFF);
  
  this->write_command_(0x2B);  // Row Address Set
  this->write_data_(y1 >> 8);
  this->write_data_(y1 & 0xFF);
  this->write_data_(y2 >> 8);
  this->write_data_(y2 & 0xFF);
  
  this->write_command_(0x2C);  // Memory Write
}

void TDeckPlusST7789::draw_absolute_pixel_internal(int x, int y, Color color) {
  if (x >= this->get_width_internal() || y >= this->get_height_internal() || x < 0 || y < 0)
    return;
  
  this->set_addr_window_(x, y, x, y);
  
  uint16_t color565 = display::ColorUtil::color_to_565(color);
  
  digitalWrite(this->dc_pin_, HIGH);
  this->enable();
  this->write_byte(color565 >> 8);
  this->write_byte(color565 & 0xFF);
  this->disable();
}

}  // namespace tdeck_plus_st7789
}  // namespace esphome
