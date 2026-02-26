import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import display, spi
from esphome.const import CONF_ID, CONF_LAMBDA, CONF_DIMENSIONS, CONF_WIDTH, CONF_HEIGHT

DEPENDENCIES = ['spi']

tdeck_plus_st7789_ns = cg.esphome_ns.namespace('tdeck_plus_st7789')
TDeckPlusST7789 = tdeck_plus_st7789_ns.class_('TDeckPlusST7789', cg.PollingComponent, display.DisplayBuffer, spi.SPIDevice)

CONFIG_SCHEMA = display.FULL_DISPLAY_SCHEMA.extend({
    cv.GenerateID(): cv.declare_id(TDeckPlusST7789),
}).extend(cv.polling_component_schema('1s')).extend(spi.spi_device_schema(cs_pin_required=True))

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await spi.register_spi_device(var, config)
    await display.register_display(var, config)
