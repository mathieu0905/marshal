package com.sdl.dxa;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sdl.dxa.api.datamodel.model.EntityModelData;
import com.sdl.dxa.api.datamodel.model.PageModelData;
import com.sdl.dxa.api.datamodel.model.util.ListWrapper;
import org.junit.Test;

import java.io.File;
import java.util.Map;

import static org.junit.Assert.assertTrue;

public class JacksonObjectMixinCompatibilityTest {

    @Test
    public void shouldDeserializePolymorphicExtensionData() throws Exception {
        ObjectMapper objectMapper = new DxaSpringInitialization().objectMapper();
        File fixture = new File("../dxa-data-model/src/test/resources/dxa20json/pageModel.json");

        PageModelData page = objectMapper.readValue(fixture, PageModelData.class);
        Map<String, Object> extensionData = page.getExtensionData();

        assertTrue(extensionData.get("EntityModelData") instanceof EntityModelData);
        assertTrue(extensionData.get("EntityModelDatas") instanceof ListWrapper);
    }
}
