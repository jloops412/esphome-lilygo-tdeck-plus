import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import display, spi
from esphome.const import (
    CONF_DC_PIN,
    CONF_ID,
    CONF_RESET_PIN,
)

CONF_BACKLIGHT_PIN = "backlight_pin"

DEPENDENCIES = ["spi"]

tdeck_plus_st7789_ns = cg.esphome_ns.namespace("tdeck_plus_st7789")
TDeckPlusST7789 = tdeck_plus_st7789_ns.class_(
    "TDeckPlusST7789", display.DisplayBuffer, spi.SPIDevice
)

CONFIG_SCHEMA = (
    display.FULL_DISPLAY_SCHEMA.extend(
        {
            cv.GenerateID(): cv.declare_id(TDeckPlusST7789),
            cv.Required(CONF_DC_PIN): cv.int_,
            cv.Optional(CONF_RESET_PIN): cv.int_,
            cv.Optional(CONF_BACKLIGHT_PIN): cv.int_,
        }
    )
    .extend(spi.spi_device_schema(cs_pin_required=True))
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await spi.register_spi_device(var, config)
    await display.register_display(var, config)

    cg.add(var.set_dc_pin(config[CONF_DC_PIN]))

    if CONF_RESET_PIN in config:
        cg.add(var.set_reset_pin(config[CONF_RESET_PIN]))

    if CONF_BACKLIGHT_PIN in config:
        cg.add(var.set_backlight_pin(config[CONF_BACKLIGHT_PIN]))
