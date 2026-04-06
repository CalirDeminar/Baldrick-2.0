from pydantic import BaseModel
from pydantic import Field
from pathlib import Path
import yaml

class ConfigOverride(BaseModel):
    name: str = Field(min_length=1)
    route_colour: str | None = Field(default="#000000")
    min_cruise_speed: int | None = Field(ge=0)
    default_cruise_speed: int | None = Field(ge=0)
    dash_speed: int | None = Field(ge=0)
    metric: bool | None = Field(default=False)

class Config(BaseModel):
    overview_card_downsample_factor: float = Field(ge=0, default=3)
    route_colour: str = Field(default="#000000")
    min_cruise_speed: int = Field(ge=0)
    default_cruise_speed: int = Field(ge=0)
    dash_speed: int = Field(ge=0)
    metric: bool = Field(default=False)
    overrides: list[ConfigOverride] = Field(default={})
    # Consideration: WP Bookmark / Shorthand library

    @staticmethod
    def from_file(path: Path) -> 'Config':
        with path.open('r') as file:
            data = yaml.load(file, Loader=yaml.SafeLoader)
            overrides: list[ConfigOverride] = [ConfigOverride(**entry) for entry in data.pop('overrides')]
            return Config(**data, overrides=overrides)

    def override(self, override: str | None) -> 'Config':
        if override is not None:
            for override_opt in self.overrides:
                if override_opt.name == override:
                    return Config(
                        overview_card_downsample_factor=self.overview_card_downsample_factor,
                        route_colour=override_opt.route_colour or self.route_colour,
                        min_cruise_speed=override_opt.min_cruise_speed or self.min_cruise_speed,
                        default_cruise_speed=override_opt.default_cruise_speed or self.default_cruise_speed,
                        dash_speed=override_opt.dash_speed or self.dash_speed,
                        metric=override_opt.metric or self.metric,
                    )
        return self

if __name__ == '__main__':
    print(Config.from_file(Path('../example_config.yaml')))
    print(Config.from_file(Path('../example_config.yaml')).override('warbirds'))