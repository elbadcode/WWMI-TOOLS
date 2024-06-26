import hashlib

from typing import List, Dict, Union
from dataclasses import dataclass, field
from pathlib import Path

from ..migoto_io.blender_interface.collections import *
from ..migoto_io.blender_interface.objects import *
from ..migoto_io.blender_interface.mesh import *

from ..migoto_io.buffers.byte_buffer import ByteBuffer

from .ini_builder.IniBuilder import IniBuilder, IniSection, SectionType, IniSectionConditional
from .metadata_collector import MeshObject, ShapeKeys, ModInfo, Texture
    

def is_ini_edited(ini_path):
    '''
    Extracts defined SHA256 CHECKSUM from provided file and calculates sha256 of remaining lines
    If hashes match, it means that file doesn't contain any manual edits
    Allows to detect if mod.ini was manually edited to prevent accidental overwrite
    '''
    with open(ini_path, 'r') as f:
        data = list(f)

        # Extract data from expected location of checksum stamp
        checksum = data[-1].strip()

        # Ensure that checksum stamp has expected prefix 
        checksum_prefix = '; SHA256 CHECKSUM: '
        if not checksum.startswith(checksum_prefix):
            return False
        
        # Extract sha256 hash value from checksum stamp
        sha256 = checksum.replace(checksum_prefix, '')
        
        # Calculate sha256 hash of all lines above checksum stamp
        ini_data = data[:-1]
        ini_sha256 = hashlib.sha256(''.join(ini_data).encode('utf-8')).hexdigest()

        # Check if checksums are matching, different sha256 means data was edited
        if ini_sha256 != sha256:
            return True

        return False


@dataclass
class IniMaker:
    # Input
    mod_info: ModInfo
    mesh_object: MeshObject
    shapekeys: ShapeKeys
    buffers: Dict[str, ByteBuffer]
    textures: List[Texture]
    comment_code: bool
    # Output
    ini: IniBuilder = field(init=False)

    def __post_init__(self):
        self.ini = IniBuilder({
            'skip_comments': not self.comment_code
        })
        self.ini.header = (
            '; WWMI ALPHA-1 INI\n\n'
        )
        self.make_mod_state_group()
        if self.shapekeys.custom_vertex_count > 0:
            self.make_shape_keys_override_group()
        self.make_skeleton_override_group()
        self.make_draw_calls_group()
        self.make_mod_info_group()
        self.make_texture_resources_group()
        self.make_buffer_resources_group()
        if self.shapekeys.custom_vertex_count > 0:
            self.make_shape_keys_resources_group()
        self.make_skeleton_resources_group()
        self.make_autogenerated_group()

    def build(self):
        return self.with_checksum(self.ini.build())
    
    def with_checksum(self, lines):
        '''
        Calculates sha256 hash of provided lines and adds following looking entry to the end:
        '; SHA256 CHECKSUM: 401cafcfdb224c5013802b3dd5a5442df5f082404a9a1fed91b0f8650d604370' + '\n'
        Allows to detect if mod.ini was manually edited to prevent accidental overwrite
        '''
        sha256 = hashlib.sha256(lines.encode('utf-8')).hexdigest()
        lines += f'; SHA256 CHECKSUM: {sha256}' + '\n'
        return lines

    def make_mod_state_group(self):
        self.ini.set_group_header(0, (
            '; Mod State -------------------------\n\n'
        ))

        # [Constants]
        constants = IniSection(
            comment='Global variables used by entire mod',
            name='',
            section_type=SectionType.Constants,
        )
        self.ini.add_section(constants, 0)

        constants.body.add_comment(r'Allows WWMI to safely disable incopatible mod and notify user about it')
        constants.body.add_command(r'global $required_wwmi_version = %.1f' % self.mod_info.required_wwmi_version.as_float())

        constants.body.add_comment(r'Number of indicies in original model')
        constants.body.add_command(r'global $object_guid = %d' % self.mesh_object.original_index_count)

        constants.body.add_comment(r'Number of verticies in custom model')
        constants.body.add_command(f'global $mesh_vertex_count = {self.mesh_object.custom_vertex_count}')

        constants.body.add_comment(r'Number of shapekeyed verticies in custom model')
        constants.body.add_command(f'global $shapekey_vertex_count = {self.shapekeys.custom_vertex_count}')

        constants.body.add_comment(r'ID assigned to our mod by WWMI')
        constants.body.add_command(r'global $mod_id = -1000')

        constants.body.add_comment(r'Controls whether our mod is enabled, prevents any overrides from happening if $mod_enabled == 0')
        constants.body.add_comment(r'Prevents user from being crash-locked in case of incompatible WWMI version')
        constants.body.add_command(r'global $mod_enabled = 0')

        # [Present]
        present = IniSection(
            comment='List of commands executed for every frame',
            name='',
            section_type=SectionType.Present,
        )
        self.ini.add_section(present, 0)

    def make_mod_info_group(self):
        self.ini.set_group_header(1, (
            '; Resources: Mod Info -------------------------\n\n'
        ))

        # [ResourceModName]
        mod_name = IniSection(
            comment='Name of mod',
            name='ModName',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(mod_name, 1)

        if len(self.mod_info.mod_name.strip()) != 0:
            mod_name.body.add_command(r'type = Buffer')
            mod_name.body.add_command(f'data = "{self.mod_info.mod_name}"')
        else:
            mod_name.body.add_persistent_comment(r'type = Buffer')
            mod_name.body.add_persistent_comment(f'data = "Unknown Mod Name"')

        # [ResourceModAuthor]
        mod_author = IniSection(
            comment='Name of mod author',
            name='ModAuthor',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(mod_author, 1)

        if len(self.mod_info.mod_author.strip()) != 0:
            mod_author.body.add_command(r'type = Buffer')
            mod_author.body.add_command(f'data = "{self.mod_info.mod_author}"')
        else:
            mod_author.body.add_persistent_comment(r'type = Buffer')
            mod_author.body.add_persistent_comment(f'data = "Unknown Mod Author"')

        # [ResourceModDesc]
        mod_desc = IniSection(
            comment='Mod description',
            name='ModDesc',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(mod_desc, 1)

        if len(self.mod_info.mod_desc.strip()) != 0:
            mod_desc.body.add_command(r'type = Buffer')
            mod_desc.body.add_command(f'data = "{self.mod_info.mod_desc}"')
        else:
            mod_desc.body.add_persistent_comment(r'type = Buffer')
            mod_desc.body.add_persistent_comment(f'data = "Empty Mod Description"')

        # [ResourceModLink]
        mod_link = IniSection(
            comment='Link to mod repository',
            name='ModLink',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(mod_link, 1)

        if len(self.mod_info.mod_link.strip()) != 0:
            mod_link.body.add_command(r'type = Buffer')
            mod_link.body.add_command(f'data = "{self.mod_info.mod_link}"')
        else:
            mod_link.body.add_persistent_comment(r'type = Buffer')
            mod_link.body.add_persistent_comment(f'data = "Empty Mod Link"')

        # [ResourceModLogo]
        mod_logo = IniSection(
            comment='Texture file with 512x512 .dds (BC7 SRGB) mod logo',
            name='ModLogo',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(mod_logo, 1)

        if self.mod_info.mod_logo.is_file():
            mod_logo.body.add_command(r'filename = Textures/Logo.dds')
        else:
            mod_logo.body.add_persistent_comment(r'filename = Textures/Logo.dds')

    def make_draw_calls_group(self):
        self.ini.set_group_header(2, (
            '; Shading: Draw Call Stacks Processing -------------------------\n\n'
        ))        

        # [CommandListOverrideSharedResources]
        replace_shared_resources = IniSection(
            comment='Overrides resources that are shared between VS calls',
            name='OverrideSharedResources',
            section_type=SectionType.CommandList,
        )
        self.ini.add_section(replace_shared_resources, 2)
        replace_shared_resources.body.add_comment(r'Override Index Buffer to make draw calls use custom faces')
        replace_shared_resources.body.add_command(r'ib = ResourceIndexBuffer')
        replace_shared_resources.body.add_comment(r'Vertex Shader Textures slots require special attention, as they can be leaked outside if unused by the call')
        replace_shared_resources.body.add_comment(r'Lets use helper funnction to ensure original vs-t slots content gonna be restored after the call')
        replace_shared_resources.body.add_command(r'run = CommandList\WWMIv1\BackupRestoreVertexTextureSlots')
        replace_shared_resources.body.add_comment(r'Override Texcoord and Color Buffers to make draw calls use custom UVs and Vertex Colors')
        replace_shared_resources.body.add_command(r'vs-t0 = ResourceTexcoordBuffer')
        replace_shared_resources.body.add_command(r'vs-t2 = ResourceColorBuffer')

        # [CommandListOverrideTextures]
        replace_textures = IniSection(
            comment='Overrides textures via triggering [ResourceTextureX] sections by calling chechtextureoverride on ps-t slots',
            name='OverrideTextures',
            section_type=SectionType.CommandList,
        )
        self.ini.add_section(replace_textures, 2)

        replace_textures.body.add_command(r'checktextureoverride = ps-t0')
        replace_textures.body.add_command(r'checktextureoverride = ps-t1')
        replace_textures.body.add_command(r'checktextureoverride = ps-t2')
        replace_textures.body.add_command(r'checktextureoverride = ps-t3')
        replace_textures.body.add_command(r'checktextureoverride = ps-t4')
        replace_textures.body.add_command(r'checktextureoverride = ps-t5')
        replace_textures.body.add_command(r'checktextureoverride = ps-t6')
        replace_textures.body.add_command(r'checktextureoverride = ps-t7')

        for component_id, component in enumerate(self.mesh_object.components):
            # [TextureOverrideComponentX]
            replace_component = IniSection(
                comment=f'Override draw calls for Component {component_id}',
                name=f'Component{component_id}',
                section_type=SectionType.TextureOverride,
                hash=self.mesh_object.vb0_hash,
            )
            self.ini.add_section(replace_component, 2)
            replace_component.body.add_command(f'match_first_index = {component.stock_component.index_offset}')
            replace_component.body.add_command(f'match_index_count = {component.stock_component.index_count}')

            mod_enabled_condition = replace_component.body.add_command(IniSectionConditional())
            mod_enabled_body = mod_enabled_condition.add_if_clause('$mod_enabled')
            mod_enabled_body.add_comment(r'Skip original draw call')
            mod_enabled_body.add_command(r'handling = skip')
            
            mod_enabled_body.add_comment(r'Override shared resources')
            mod_enabled_body.add_command(f'run = {replace_shared_resources.get_section_title()}')

            mod_enabled_body.add_comment(r'Override textures')
            mod_enabled_body.add_command(f'run = {replace_textures.get_section_title()}')

            if component.custom_component is not None:
                for sub_component in component.custom_component.components:
                    mod_enabled_body.add_persistent_comment(f'Draw {sub_component.name}')
                    mod_enabled_body.add_command(r'drawindexed = %d, %d, 0' % (sub_component.index_count, 
                                                                            sub_component.index_offset))
            else:
                mod_enabled_body.add_persistent_comment(f'Draw skipped: No matching custom components found')

    def make_texture_resources_group(self):
        self.ini.set_group_header(3, (
            '; Shading: Textures -------------------------\n\n'
        ))

        for texture_id, texture in enumerate(self.textures):

            texture_resoruce = IniSection(
                name=f'Texture{texture_id}',
                section_type=SectionType.Resource,
            )
            self.ini.add_section(texture_resoruce, 3)

            texture_resoruce.body.add_command(f'filename = Textures/{texture.filename}')

            texture_override = IniSection(
                name=f'Texture{texture_id}',
                hash=texture.hash,
                section_type=SectionType.TextureOverride,
            )
            self.ini.add_section(texture_override, 3)

            texture_override.body.add_command(f'match_priority = 0')
            texture_override.body.add_command(f'this = {texture_resoruce.get_section_title()}')

    def make_shape_keys_override_group(self):
        self.ini.set_group_header(4, (
            '; Skinning: Shape Keys Override -------------------------\n\n'
        ))
        
        # [TextureOverrideVertexLimitRaiseShapeKeyOffsets]
        raise_shape_key_offsets = IniSection(
            comment='Increases size of UAV that stores shapekeyed vertices xyz offsets to support more vertices than original',
            name='VertexLimitRaiseShapeKeyOffsets',
            section_type=SectionType.TextureOverride,
            hash=self.shapekeys.offsets_hash,
        )
        self.ini.add_section(raise_shape_key_offsets, 4)

        raise_shape_key_offsets.body.add_command(r'match_priority = 0')
                
        # [TextureOverrideVertexLimitRaiseShapeKeyScale]
        raise_shape_key_scale = IniSection(
            comment='Increases size of UAV that stores shapekeyed vertices multipliers to support more vertices than original',
            name='VertexLimitRaiseShapeKeyScale',
            section_type=SectionType.TextureOverride,
            hash=self.shapekeys.scale_hash,
        )
        self.ini.add_section(raise_shape_key_scale, 4)

        raise_shape_key_scale.body.add_command(r'match_priority = 0')

        
        # [CommandListSetupShapeKeys]
        setup_shapekeys = IniSection(
            comment='Updates ResourceShapeKeyCBRW that stores offsets of shapekeyed vertex lists, shape key values and multipliers',
            name='SetupShapeKeys',
            section_type=SectionType.CommandList,
        )
        self.ini.add_section(setup_shapekeys, 4)

        setup_shapekeys.body.add_comment(r'Pass 4 byte checksum of shapekey offsets to ensure that we only modify expected values')
        setup_shapekeys.body.add_command(f'$\WWMIv1\shapekey_checksum = {self.shapekeys.checksum}')
        setup_shapekeys.body.add_comment(r'Pass buffer with offsets for vertex lists of every shape key of custom model')
        setup_shapekeys.body.add_command(r'cs-t33 = ResourceShapeKeyOffsetBuffer')
        setup_shapekeys.body.add_comment(r'Pass buffer with custom values for every shape key, allows to control both custom and stock')
        setup_shapekeys.body.add_command(r'cs-u5 = ResourceCustomShapeKeyValuesRW')
        setup_shapekeys.body.add_comment(r'Pass buffer that gonna store result of calculations, required for Shape Key Loader CS to run')
        setup_shapekeys.body.add_command(r'cs-u6 = ResourceShapeKeyCBRW')

        setup_shapekeys.body.add_comment(r'Run ShapeKeyOverrider CS')
        setup_shapekeys.body.add_command(r'run = CustomShader\WWMIv1\ShapeKeyOverrider')
        
        # [CommandListLoadShapeKeys]
        load_shapekeys = IniSection(
            comment='Runs custom Shape Key Loader CS to, well, load shapekeys data from buffers',
            name='LoadShapeKeys',
            section_type=SectionType.CommandList,
        )
        self.ini.add_section(load_shapekeys, 4)

        load_shapekeys.body.add_comment(r'Pass number of shapekeyed vertices to adjust required threads count via dipatch_y')
        load_shapekeys.body.add_command(f'$\WWMIv1\shapekey_vertex_count = $shapekey_vertex_count')

        load_shapekeys.body.add_comment(r'Pass buffer with lists of per-vertex ids for every shape key')
        load_shapekeys.body.add_command(r'cs-t0 = ResourceShapeKeyVertexIdBuffer')
        load_shapekeys.body.add_comment(r'Pass buffer with lists of xyz per-vertex offsets for every shape key')
        load_shapekeys.body.add_command(r'cs-t1 = ResourceShapeKeyVertexOffsetBuffer')
        load_shapekeys.body.add_comment(r'Pass buffer with shape key vertex lists offsets, and shape key values & multipliers')
        load_shapekeys.body.add_command(r'cs-u6 = ResourceShapeKeyCBRW')

        load_shapekeys.body.add_comment(r'Run ShapeKeyLoader CS')
        load_shapekeys.body.add_command(r'run = CustomShader\WWMIv1\ShapeKeyLoader')

        # [TextureOverrideShapeKeyLoaderCallback]
        loader_cs_callback = IniSection(
            comment='Handles WWMI callback fired on original Shape Key Loader CS call',
            name='ShapeKeyLoaderCallback',
            section_type=SectionType.TextureOverride,
            hash=self.shapekeys.offsets_hash,
        )
        self.ini.add_section(loader_cs_callback, 4)

        loader_cs_callback.body.add_command(r'match_priority = 0')

        mod_enabled_condition = loader_cs_callback.body.add_command(IniSectionConditional())
        mod_enabled_body = mod_enabled_condition.add_if_clause('$mod_enabled')

        mod_enabled_body.add_comment(r'Ensure that callback has WWMI filter_index of Shape Key Loader CS assigned')
        loader_callback_condition = mod_enabled_body.add_command(IniSectionConditional())
        loader_cs_body = loader_callback_condition.add_if_clause('cs == 3381.3333')

        # It looks like we can skip checking for THREAD_GROUP_COUNT_Y as UAV hashes are unique for each object
        # loader_cs_body.add_comment(r'Ensure that dispatch_y of Shape Key Loader CS call matches one from dump')
        # run_loader_condition = loader_cs_body.add_command(IniSectionConditional())
        # run_loader_body = run_loader_condition.add_if_clause(f'THREAD_GROUP_COUNT_Y == {self.shapekeys.loader_dispatch_y}')
        loader_cs_body.add_comment(r'Skip handling of original Shape Key Loader CS call to modify dispatch_y value')
        loader_cs_body.add_command(r'handling = skip')
        loader_cs_body.add_comment(r'Run custom Shape Key Overrider CS to prepare shape key resources for loading')
        loader_cs_body.add_command(f'run = {setup_shapekeys.get_section_title()}')
        loader_cs_body.add_comment(r'Run custom Shape Key Loader CS to load shape key resources')
        loader_cs_body.add_command(f'run = {load_shapekeys.get_section_title()}')

        # [CommandListMultiplyShapeKeys]
        multiply_shapekeys = IniSection(
            comment='Runs custom Shape Key Loader CS to, well, load shapekeys data from buffers',
            name='MultiplyShapeKeys',
            section_type=SectionType.CommandList,
        )
        self.ini.add_section(multiply_shapekeys, 4)
        multiply_shapekeys.body.add_comment(r'Pass number of shapekeyed vertices to adjust required threads count via dipatch_y')
        multiply_shapekeys.body.add_command(r'$\WWMIv1\shapekey_vertex_count = $shapekey_vertex_count')
        multiply_shapekeys.body.add_comment(r'Run custom Shape Key Multiplier CS to set deformation intensity')
        multiply_shapekeys.body.add_command(r'run = CustomShader\WWMIv1\ShapeKeyMultiplier')

        # [TextureOverrideShapeKeyMultiplierCallback]
        multiplier_cs_callback = IniSection(
            comment='Handles WWMI callback fired on original Shape Key Multiplier CS call',
            name='ShapeKeyMultiplierCallback',
            section_type=SectionType.TextureOverride,
            hash=self.shapekeys.offsets_hash,
        )
        self.ini.add_section(multiplier_cs_callback, 4)

        multiplier_cs_callback.body.add_command(r'match_priority = 0')

        mod_enabled_condition = multiplier_cs_callback.body.add_command(IniSectionConditional())
        mod_enabled_body = mod_enabled_condition.add_if_clause('$mod_enabled')

        mod_enabled_body.add_comment(r'Ensure that callback has WWMI filter_index of Shape Key Multiplier CS assigned')
        multiplier_callback_condition = mod_enabled_body.add_command(IniSectionConditional())
        multiplier_cs_body = multiplier_callback_condition.add_if_clause('cs == 3381.4444')

        # It looks like we can skip checking for THREAD_GROUP_COUNT_Y as UAV hashes are unique for each object
        # multiplier_cs_body.add_comment(r'Ensure that dispatch_y of Shape Key Multiplier CS call matches one from dump')
        # multiplier_condition = multiplier_cs_body.add_command(IniSectionConditional())
        # run_multiplier_body = multiplier_condition.add_if_clause(f'THREAD_GROUP_COUNT_Y == {self.shapekeys.multiplier_dispatch_y}')
        multiplier_cs_body.add_comment(r'Skip handling of original Shape Key Multiplier CS call to modify dispatch_y value')
        multiplier_cs_body.add_command(r'handling = skip')
        multiplier_cs_body.add_comment(r'Run custom Shape Key Multiplier CS to apply dynamic per-character multipliers')
        multiplier_cs_body.add_command(f'run = {multiply_shapekeys.get_section_title()}')

    def make_skeleton_override_group(self):
        self.ini.set_group_header(5, (
            '; Skinning: Skeleton Override -------------------------\n\n'
        ))
        
        # [TextureOverrideVertexLimitRaiseVB0]
        vertex_limit_raise_vb0 = IniSection(
            comment='Increases size of UAV that stores VB0 to support more vertices than original',
            name='VertexLimitRaiseVB0',
            section_type=SectionType.TextureOverride,
            hash=self.mesh_object.vb0_hash,
        )
        self.ini.add_section(vertex_limit_raise_vb0, 5)

        vertex_limit_raise_vb0.body.add_command(r'match_priority = 0')
        
        # [TextureOverrideVertexLimitRaiseVB1]
        vertex_limit_raise_vb1 = IniSection(
            comment='Increases size of UAV that stores VB1 to support more vertices than original',
            name='VertexLimitRaiseVB1',
            section_type=SectionType.TextureOverride,
            hash=self.mesh_object.vb1_hash,
        )
        self.ini.add_section(vertex_limit_raise_vb1, 5)

        vertex_limit_raise_vb1.body.add_command(r'match_priority = 0')

        # [CommandListRegisterMod]
        register_mod = IniSection(
            comment='Contacts WWMI to check whether installed version is compatible with our mod',
            name='RegisterMod',
            section_type=SectionType.CommandList,
        )
        self.ini.add_section(register_mod, 5)

        register_mod.body.add_comment(r'Pass mod info variables to WWMI')
        register_mod.body.add_command(r'$\WWMIv1\required_wwmi_version = $required_wwmi_version')
        register_mod.body.add_command(r'$\WWMIv1\object_guid = $object_guid')

        register_mod.body.add_comment(r'Pass mod info resources to WWMI')
        register_mod.body.add_command(r'Resource\WWMIv1\ModName = ref ResourceModName')
        register_mod.body.add_command(r'Resource\WWMIv1\ModAuthor = ref ResourceModAuthor')
        register_mod.body.add_command(r'Resource\WWMIv1\ModDesc = ref ResourceModDesc')
        register_mod.body.add_command(r'Resource\WWMIv1\ModLink = ref ResourceModLink')
        register_mod.body.add_command(r'Resource\WWMIv1\ModLogo = ref ResourceModLogo')

        register_mod.body.add_comment(r'Register mod in WWMI')
        register_mod.body.add_command(r'run = CommandList\WWMIv1\RegisterMod')

        register_mod.body.add_comment(r'Read mod_id assigned to our mod by WWMI, incompatible mod will get `$mod_id == -1` assigned')
        register_mod.body.add_command(r'$mod_id = $\WWMIv1\mod_id')

        register_mod.body.add_comment(r'Enable our mod if WWMI assigned valid $mod_id to it')
        valid_mod_id_condition = register_mod.body.add_command(IniSectionConditional())
        valid_mod_id_body = valid_mod_id_condition.add_if_clause('$mod_id >= 0')
        valid_mod_id_body.add_command(r'$mod_enabled = 1')
        
        # [CommandListMergeSkeleton]
        merge_skeleton = IniSection(
            comment='Update ResourceMergedSkeletonRW with bones data of current component',
            name='MergeSkeleton',
            section_type=SectionType.CommandList,
        )
        self.ini.add_section(merge_skeleton, 5)

        merge_skeleton.body.add_comment(r'Pass buffer that gonna store bone data of all components')
        merge_skeleton.body.add_command(r'cs-u6 = ResourceMergedSkeletonRW')

        merge_skeleton.body.add_comment(r'Run Skeleton Merger CS to merge bones of current component into ResourceMergedSkeletonRW')
        merge_skeleton.body.add_command(r'run = CustomShader\WWMIv1\SkeletonMerger')
        
        # [CommandListSkinMesh]
        skin_mesh = IniSection(
            comment='Pose entire mesh with merged skeleton using custom WWMI Pose CS',
            name='SkinMesh',
            section_type=SectionType.CommandList,
        )
        self.ini.add_section(skin_mesh, 5)

        skin_mesh.body.add_comment(r'Set vertex id to start skinning from, for output integrity we have to skin entire mesh every time')
        skin_mesh.body.add_command(r'$\WWMIv1\custom_vertex_offset = 0')
        skin_mesh.body.add_comment(r'Set number of vertices for skinning, for output integrity we have to skin entire mesh every time')
        skin_mesh.body.add_command(r'$\WWMIv1\custom_vertex_count = $mesh_vertex_count')
        skin_mesh.body.add_comment(r'Set arbitrary scale for our custom model')
        skin_mesh.body.add_command(r'$\WWMIv1\custom_mesh_scale = 1.0')

        skin_mesh.body.add_comment(r'Pass resources for Mesh Skinner CS')
        skin_mesh.body.add_command(r'cs-t3 = ResourceShapeKeyDataRef')
        skin_mesh.body.add_command(r'cs-t4 = ResourceBlendBuffer')
        skin_mesh.body.add_command(r'cs-t5 = ResourceVectorBuffer')
        skin_mesh.body.add_command(r'cs-t6 = ResourcePositionBuffer')

        skin_mesh.body.add_comment(r'Run Mesh Skinner CS')
        skin_mesh.body.add_command(r'run = CustomShader\WWMIv1\MeshSkinner')

        # [TextureOverrideMeshSkinnerCallback]
        register_callback = IniSection(
            comment='Handles WWMI callback fired on original Basis or ShapeKeyed Mesh Skinner CS call',
            name='MeshSkinnerCallback',
            section_type=SectionType.TextureOverride,
            hash=self.mesh_object.vb0_hash,
        )
        self.ini.add_section(register_callback, 5)
        register_callback.body.add_command(r'match_priority = 0')
        
        register_callback.body.add_comment(r'Check if our mod is compatible with installed WWMI version (runs only once)')
        mod_id_condition = register_callback.body.add_command(IniSectionConditional())
        mod_id_body = mod_id_condition.add_if_clause('$mod_id == -1000')

        mod_id_body.add_comment(r'Pass required WWMI version along with mod metadata to WWMI')
        mod_id_body.add_command(r'run = CommandListRegisterMod')

        mod_enabled_condition = register_callback.body.add_command(IniSectionConditional())
        mod_enabled_body = mod_enabled_condition.add_if_clause('$mod_enabled')

        mod_enabled_body.add_comment(r'Ensure that callback has WWMI filter_index of Basis or ShapeKeyed Pose CS assigned')
        pose_cs_condition = mod_enabled_body.add_command(IniSectionConditional())
        pose_cs_body = pose_cs_condition.add_if_clause('cs == 3381.1111 || cs == 3381.2222')

        pose_cs_body.add_comment(r'Skip handling of original Pose CS call as we may need to modify dispatch_x value')
        pose_cs_body.add_command(r'handling = skip')

        pose_cs_body.add_comment(r'Check if it is a ShapeKeyed Pose CS call')
        pose_cs_condition = pose_cs_body.add_command(IniSectionConditional())

        shapekeyed_pose_cs_body = pose_cs_condition.add_if_clause('cs == 3381.2222')
        shapekeyed_pose_cs_body.add_comment(r'Store reference to shapekey data so it can be used with Basis Pose CS call as well')
        shapekeyed_pose_cs_body.add_command(r'ResourceShapeKeyDataRef = ref cs-t3')

        for component_id, component in enumerate(self.mesh_object.components):
            pose_cs_body.add_comment(f'Handle Component {component_id}')
            merge_skeleton_condition = pose_cs_body.add_command(IniSectionConditional())
            merge_skeleton_body = merge_skeleton_condition.add_if_clause(f'THREAD_GROUP_COUNT_X == {component.dispatch_x}')
            merge_skeleton_body.add_comment(r'Pass variables for SkeletonMerger CS')
            merge_skeleton_body.add_command(r"$\WWMIv1\original_vertex_offset = %d" % component.stock_component.vertex_offset)
            merge_skeleton_body.add_command(r"$\WWMIv1\original_vertex_count = %d" % component.stock_component.vertex_count)
            merge_skeleton_body.add_command(r"$\WWMIv1\vg_offset = %d" % component.stock_component.vg_offset)
            merge_skeleton_body.add_command(r"$\WWMIv1\vg_count = %d" % component.stock_component.vg_count)
            merge_skeleton_body.add_comment(r'Merge bones of this components into ResourceMergedSkeleton')
            merge_skeleton_body.add_command(r"run = CommandListMergeSkeleton")
            merge_skeleton_body.add_comment(r'Pose entire mesh with custom pose CS')
            merge_skeleton_body.add_command(r"run = CommandListSkinMesh")

    def make_buffer_resources_group(self):
        self.ini.set_group_header(6, (
            '; Resources: Buffers -------------------------\n\n'
        ))

        for buffer_name, buffer in self.buffers.items():

            buffer_resource = IniSection(
                name=f'{buffer_name}Buffer',
                section_type=SectionType.Resource,
            )
            self.ini.add_section(buffer_resource, 6)
            buffer_resource.body.add_command(r'type = Buffer')
            buffer_resource.body.add_command(f'format = {buffer.layout.semantics[0].get_format()}')
            buffer_resource.body.add_command(f'filename = Meshes/{buffer_name}.buf')
   
    def make_shape_keys_resources_group(self):
        self.ini.set_group_header(7, (
            '; Resources: Shape Keys Override -------------------------\n\n'
        ))

        # [ResourceShapeKeyCBRW]
        shapekey_cb = IniSection(
            comment='Stores dynamically calculated CB required to override original Shape Keys CS call',
            name='ShapeKeyCBRW',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(shapekey_cb, 7)
        shapekey_cb.body.add_comment(r'Contains 128+128+8 values:')
        shapekey_cb.body.add_comment(r'* 128 uint: Shape Key offsets (continuous lists of vertex offsets)')
        shapekey_cb.body.add_comment(r'* 128 unorm: Shape Key values (range [0.0, 1.0])')
        shapekey_cb.body.add_comment(r'* 8 uint: Shape Key CS settings')
        shapekey_cb.body.add_command(r'type = RWBuffer')
        shapekey_cb.body.add_command(r'format = R32G32B32A32_UINT')
        shapekey_cb.body.add_comment(r'32 shapekey offsets, 32 shapekey values, 2 control flags')
        shapekey_cb.body.add_command(r'array = 66')

        # [ResourceCustomShapeKeyValuesRW]
        custom_values = IniSection(
            comment='Stores values of custom Shape Keys and overrides for original ones',
            name='CustomShapeKeyValuesRW',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(custom_values, 7)
        custom_values.body.add_comment(r'Contains 128 values, zero is shifted by 1.0 to the right')
        custom_values.body.add_comment(r'Expected value range is [1.0, 2.0]')
        custom_values.body.add_comment(r'* `0.0` means `no override`')
        custom_values.body.add_comment(r'* `1.0` means `override with zero`')
        custom_values.body.add_comment(r'* `2.0` means `override with one`')
        custom_values.body.add_command(r'type = RWBuffer')
        custom_values.body.add_command(r'format = R32G32B32A32_FLOAT')
        custom_values.body.add_comment(r'32 elements, 4 floats per element')
        custom_values.body.add_command(r'array = 32')

    def make_skeleton_resources_group(self):
        self.ini.set_group_header(8, (
            '; Resources: Skeleton Override -------------------------\n\n'
        ))

        # [ResourceShapeKeyDataRef]
        shapekey_data_ref = IniSection(
            comment='Stores reference to dynamic data (xyz coords offsets) generated by Shape Key CS',
            name='ShapeKeyDataRef',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(shapekey_data_ref, 8)

        # [ResourceMergedSkeletonRW]
        merged_skeleton = IniSection(
            comment='Stores merged skeleton consisting of bones from all components, allows to make VG weights global',
            name='MergedSkeletonRW',
            section_type=SectionType.Resource,
        )
        self.ini.add_section(merged_skeleton, 8)

        merged_skeleton.body.add_comment(r'Contains up to 256 bones')
        merged_skeleton.body.add_command(r'type = RWBuffer')
        merged_skeleton.body.add_command(r'format = R32G32B32A32_FLOAT')
        merged_skeleton.body.add_comment(r'256 bones, 3 elements per bone, 4 floats per element')
        merged_skeleton.body.add_command(r'array = 768')

    def make_autogenerated_group(self):
        msg = 'This mod.ini was automatically generated by WWMI Tools Blender addon v%s and requires WWMI v%s+ to function' % (
            self.mod_info.wwmi_tools_version, self.mod_info.required_wwmi_version
        )
        self.ini.set_group_footer(8, (
            '\n'
            '; Autogenerated -------------------------\n'
            '\n'
            f'; {msg}' + '\n'
            '; WWMI Link: https://gamebanana.com/mods/xxxxxx' + '\n'
            '; WWMI GitHub: https://github.com/SpectrumQT/WWMI' + '\n'
            '; WWMI Tools Link: https://gamebanana.com/mods/xxxxxx' + '\n'
            '; WWMI Tools GitHub: https://github.com/SpectrumQT/WWMI_Tools' + '\n'
            '; AGMG Modding Community Discord: https://discord.com/invite/agmg' + '\n'
            '\n'
        ))
    
