from __future__ import nested_scopes

from Products.CMFPlone import cmfplone_globals
from Products.CMFPlone import custom_policies
from Products.CMFPlone import PloneFolder
from Products.CMFPlone import ToolNames
from Products.CMFPlone import LargePloneFolder
from Products.CMFDefault.Portal import CMFSite
from Products.CMFDefault import Document

def listPolicies():
    """ Float default plone to the top """
    keys = custom_policies.keys()
    del keys[keys.index('Default Plone')]
    keys.insert(0, 'Default Plone')
    return keys

def addPolicy(label, klass): custom_policies[label]=klass

from Products.SiteErrorLog.SiteErrorLog import manage_addErrorLog
from Products.CMFCore import CMFCorePermissions
from Products.CMFCore.TypesTool import ContentFactoryMetadata, FactoryTypeInformation
from Products.CMFCore.DirectoryView import addDirectoryViews, registerDirectory
from Products.CMFCore.utils import getToolByName, registerIcon
from Products.CMFDefault import Portal, DublinCore
from Products.ExternalMethod import ExternalMethod
from PloneFolder import OrderedContainer
import Globals
import string
import os, sys, re

__version__='1.1'

default_frontpage=r"""
You can customize this frontpage by clicking the edit tab on this document if you
have the correct permissions. Create folders and put content in those folders.
Folders will show up in the navigation box if they are published. It's a very
simple and powerful system.

For more information:

"Plone website":http://www.plone.org

"Zope community":http://www.zope.org

"CMF website":http://cmf.zope.org

There are "mailing lists":http://plone.org/development/lists and
"recipe websites":http://www.zopelabs.com
available to provide assistance to you and your new-found Content Management System.
"Online chat":http://plone.org/development/chat is also a nice way
of getting advice and help.

Please contribute your experiences at the "Plone website":http://www.plone.org

Thanks for using our product.

"The Plone Team":http://plone.org/about/team
"""

factory_type_information = { 'id'             : 'Plone Root'
  , 'meta_type'      : 'Plone Site'
  , 'description'    : """ The portal_type for the root object in a Plone system."""
  , 'icon'           : 'folder_icon.gif'
  , 'product'        : 'CMFPlone'
  , 'factory'        : 'manage_addSite'
  , 'filter_content_types' : 0
  , 'global_allow'   : 0
  , 'immediate_view' : 'folder_edit_form'
  , 'actions'        : ( { 'id'            : 'view'
                         , 'name'          : 'View'
                         , 'action': 'string:${object_url}'
                         , 'permissions'   : (CMFCorePermissions.View,)
                         , 'category'      : 'folder'
                         }
                       , { 'id'            : 'edit'
                         , 'name'          : 'Properties'
                         , 'action': 'string:${object_url}/folder_edit_form'
                         , 'permissions'   : (CMFCorePermissions.ManageProperties,)
                         , 'category'      : 'folder'
                         }
                       , { 'id'            : 'localroles'
                         , 'name'          : 'Sharing'
                         , 'action':
                                  'string:${object_url}/folder_localrole_form'
                         , 'permissions'   : (CMFCorePermissions.ManageProperties,)
                         , 'category'      : 'folder'
                         }
                       )
  }

class PloneSite(CMFSite, OrderedContainer):
    """
    Make PloneSite subclass CMFSite and add some methods.
    This will be useful for adding more things later on.
    """
    meta_type = 'Plone Site'
    manage_addPloneFolder = PloneFolder.addPloneFolder
    __implements__ = ( DublinCore.DefaultDublinCoreImpl.__implements__,
                       OrderedContainer.__implements__ )

    def __browser_default__(self, request):
        """ Set default so we can return whatever we want instead
        of index_html """
        return self.browserDefault()

class PloneGenerator(Portal.PortalGenerator):

    klass = PloneSite

    def customizePortalTypes(self, p):
        typesTool=getToolByName(p, 'portal_types')
        typesTool._delObject('Folder')
        typesTool.manage_addTypeInformation(FactoryTypeInformation.meta_type,
                                            id='Folder',
                                            typeinfo_name='CMFPlone: Plone Folder')
        typesTool.manage_addTypeInformation(FactoryTypeInformation.meta_type,
                                            id='Large Plone Folder',
                                            typeinfo_name='CMFPlone: Large Plone Folder')
        typesToSkip=['Folder', 'Discussion Item', 'Topic']
        for contentType in typesTool.listContentTypes():
            typeInfo=typesTool.getTypeInfo(contentType)
            if typeInfo.getId() not in typesToSkip:
                typeObj=getattr(typesTool, typeInfo.getId())
                view=typeInfo.getActionById('view')
                typeObj._setPropValue('immediate_view', view)
            if typeInfo.getId()=='Folder':
                typeObj=getattr(typesTool, typeInfo.getId())
                view='folder_contents'
                typeObj._setPropValue('immediate_view', view)
                _actions=typeInfo._cloneActions()
                for action in _actions:
                    if action.id=='edit':
                        action.title='properties'
                typeObj._actions=_actions

    def customizePortalOptions(self, p):
        p.manage_permission( CMFCorePermissions.ListFolderContents, \
                             ('Manager', 'Member', 'Owner',), acquire=1 )
        p.portal_skins.default_skin='Plone Default'
        p.portal_skins.allow_any=1

        p.icon = 'misc_/CMFPlone/plone_icon'


    def setupPortalContent(self, p):
        p.manage_delObjects('Members')
        LargePloneFolder.addLargePloneFolder(p, 'Members')

        p.portal_catalog.unindexObject(p.Members) #unindex Members folder
        p.Members._setPortalTypeName( 'Folder' )
        Document.addDocument(p, 'index_html')
        o = p.index_html
        o._setPortalTypeName( 'Document' )
        o.setTitle('Welcome to Plone')
        o.setDescription('This welcome page is used to introduce you'+\
                         ' to the Plone Content Management System.')
        o.edit('structured-text', default_frontpage)

        o = p.Members
        o.setTitle('Members')
        o.setDescription("Container for portal members' home directories")


    def setupPloneWorkflow(self, p):
        wf_tool=p.portal_workflow
        wf_tool.manage_addWorkflow( id='plone_workflow'
                                  , workflow_type='plone_workflow '+\
                                    '(Default Workflow [Plone])')
        wf_tool.setDefaultChain('plone_workflow')

        wf_tool.manage_addWorkflow( id='folder_workflow'
                                , workflow_type='folder_workflow '+\
                                  '(Folder Workflow [Plone])')
        wf_tool.setChainForPortalTypes( ('Folder','Topic'), 'folder_workflow')

    def setupSecondarySkin(self, skin_tool, skin_title, directory_id):
        path=[elem.strip() for elem in \
              skin_tool.getSkinPath('Plone Default').split(',')]
        path.insert(path.index('custom')+1, directory_id)
        skin_tool.addSkinSelection(skin_title, ','.join(path))

    def setupPloneSkins(self, p):
        sk_tool=p.portal_skins

        # get cmf Basic skin layer definition
        path=[elem.strip() for elem in sk_tool.getSkinPath('Basic').split(',')]

        # filter out cmfdefault_layers
        existing_layers=sk_tool.objectIds()
        cmfdefault_layers=('zpt_topic', 'zpt_content', 'zpt_generic',
                           'zpt_control', 'topic', 'content', 'generic',
                           'control', 'Images', 'no_css', 'nouvelle')
        for layer in cmfdefault_layers:
            # make sure that the only remove the layer if it not
            # exists or its a Filesystem Directory View
            # to avoid deleting of custom layers
            remove = 0
            l_ob = getattr(sk_tool, layer, None)
            if not l_ob or getattr(l_ob, 'meta_type', None) == \
                   'Filesystem Directory View':
                remove = 1
            # remove from layer definition
            if layer in path and remove: path.remove(layer)
            # remove from skin tool
            if layer in existing_layers and remove:
                sk_tool.manage_delObjects(ids=[layer])

        # add plone layers
        for plonedir in ( 'cmf_legacy'
                    , 'plone_content'
                    , 'plone_images'
                    , 'plone_forms'
                    , 'plone_scripts'
                    , 'plone_form_scripts'
                    , 'plone_styles'
                    , 'plone_templates'
                    , 'plone_3rdParty/CMFCollector'
                    , 'plone_3rdParty/CMFTopic'
                    , 'plone_3rdParty/CMFCalendar'
                    , 'plone_templates'
                    , 'plone_portlets'
                    , 'plone_prefs'
                    , 'plone_wysiwyg'
                    , 'plone_ecmascript' ):
            try:
                path.insert( path.index( 'custom')+1, plonedir )
            except ValueError:
                path.append( plonedir )

        path=','.join(path)
        sk_tool.addSkinSelection('Plone Default', path)

        self.setupSecondarySkin(sk_tool, 'Plone Autumn',
                                'plone_styles/autumn')
        self.setupSecondarySkin(sk_tool, 'Plone Core',
                                'plone_styles/core')
        self.setupSecondarySkin(sk_tool, 'Plone Core Inverted',
                                'plone_styles/core_inverted')
        self.setupSecondarySkin(sk_tool, 'Plone Corporate',
                                'plone_styles/corporate')
        self.setupSecondarySkin(sk_tool, 'Plone Greensleeves',
                                'plone_styles/greensleeves')
        self.setupSecondarySkin(sk_tool, 'Plone Kitty',
                                'plone_styles/kitty')
        self.setupSecondarySkin(sk_tool, 'Plone Mozilla',
                                'plone_styles/mozilla')
        self.setupSecondarySkin(sk_tool, 'Plone Mozilla New',
                                'plone_styles/mozilla_new')
        self.setupSecondarySkin(sk_tool, 'Plone Prime',
                                'plone_styles/prime')
        self.setupSecondarySkin(sk_tool, 'Plone Zed',
                                'plone_styles/zed')

        addDirectoryViews( sk_tool, 'skins', cmfplone_globals )

        sk_tool.request_varname='plone_skin'

    def setupForms(self, p):
        """ This is being deprecated.  Please see CMFFormController """

        prop_tool = p.portal_properties
        prop_tool.manage_addPropertySheet('navigation_properties', \
                                          'Navigation Properties')
        prop_tool.manage_addPropertySheet('form_properties', 'Form Properties')

        form_tool = p.portal_form
        form_tool.setValidators('link_edit_form', \
                                ['validate_id', 'validate_link_edit'])
        form_tool.setValidators('newsitem_edit_form', \
                                ['validate_id', 'validate_newsitem_edit'])
        form_tool.setValidators('document_edit_form', \
                                ['validate_id', 'validate_document_edit'])
        form_tool.setValidators('image_edit_form', \
                                ['validate_id', 'validate_image_edit'])
        form_tool.setValidators('file_edit_form', \
                                ['validate_id', 'validate_file_edit'])
        form_tool.setValidators('folder_edit_form', \
                                ['validate_id', 'validate_folder_edit'])
        form_tool.setValidators('event_edit_form', \
                                ['validate_id', 'validate_event_edit'])
        form_tool.setValidators('topic_edit_form', \
                                ['validate_id', 'validate_topic_edit'])
        form_tool.setValidators('content_status_history', \
                                ['validate_content_status_modify'])
        form_tool.setValidators('reconfig_form', \
                                ['validate_reconfig'])
        form_tool.setValidators('personalize_form', \
                                ['validate_personalize'])
        form_tool.setValidators('join_form', \
                                ['validate_registration'])
        form_tool.setValidators('metadata_edit_form', \
                                ['validate_metadata_edit'])
        form_tool.setValidators('sendto_form', \
                                ['validate_sendto'])
        form_tool.setValidators('folder_rename_form', \
                                ['validate_folder_rename'])

        #set up properties for StatelessTreeNav
        from Products.CMFPlone.StatelessTreeNav \
             import setupNavTreePropertySheet
        setupNavTreePropertySheet(prop_tool)

        # grab the initial portal navigation properties
        # from data/navigation_properties
        nav_tool = getToolByName(p, 'portal_navigation')

        # open and parse the file
        filename='navigation_properties'
        src_file = open(os.path.join(Globals.package_home(globals()),
                                     'data', filename), 'r')
        src_lines = src_file.readlines()
        src_file.close()

        re_comment = re.compile(r"\s*#")
        re_blank = re.compile(r"\s*\n")
        re_transition = re.compile(r"\s*(?P<type>[^\.]*)\.(?P<page>[^\.]*)\.(?P<outcome>[^\s]*)\s*=\s*(?P<action>[^$]*)$")
        for line in src_lines:
            line = line.strip()
            if not re_comment.match(line) and not re_blank.match(line):
                match = re_transition.match(line)
                if match:
                    nav_tool.addTransitionFor(match.group('type'),
                                              match.group('page'),
                                              match.group('outcome'),
                                              match.group('action'))
                else:
                    sys.stderr.write("Unable to parse '%s' in navigation properties file" % (line))

    def setupPlone(self, p):
        self.customizePortalTypes(p)
        self.customizePortalOptions(p)
        self.setupPloneWorkflow(p)
        self.setupPloneSkins(p)
        self.setupPortalContent(p)
        self.setupForms(p)
        manage_addErrorLog(p)

        m = p.portal_migration

        # XXX we need to make this read version.txt
        m.setInstanceVersion('1.1') #.1')
        from migrations.plone1_1 import make_plone
        make_plone(p)
        #we no longer use migrations to setupPlone in the generator
        #m.upgrade(swallow_errors=0)

    def setupTools(self, p):
        """Set up initial tools"""

        addCMFPloneTool = p.manage_addProduct['CMFPlone'].manage_addTool
        addCMFPloneTool(ToolNames.ActionsTool, None)
        addCMFPloneTool(ToolNames.CatalogTool, None)
        #Add unwrapobjects boolean which will toggle whether or not
        #the catalog needs to unwrap objects before indexing
        p.portal_catalog._setProperty('unwrapobjects', 1, 'boolean')

        addCMFPloneTool(ToolNames.MemberDataTool, None)
        addCMFPloneTool(ToolNames.SkinsTool, None)
        addCMFPloneTool(ToolNames.TypesTool, None)
        addCMFPloneTool(ToolNames.UndoTool, None)
        addCMFPloneTool(ToolNames.URLTool, None)
        addCMFPloneTool(ToolNames.WorkflowTool, None)

        addCMFPloneTool(ToolNames.DiscussionTool, None)
        addCMFPloneTool(ToolNames.MembershipTool, None)
        addCMFPloneTool(ToolNames.RegistrationTool, None)
        addCMFPloneTool(ToolNames.PropertiesTool, None)
        addCMFPloneTool(ToolNames.MetadataTool, None)
        addCMFPloneTool(ToolNames.SyndicationTool, None)

        addCMFPloneTool(ToolNames.UtilsTool, None)
        addCMFPloneTool(ToolNames.NavigationTool, None)
        addCMFPloneTool(ToolNames.FactoryTool, None)
        addCMFPloneTool(ToolNames.FormTool, None)
        addCMFPloneTool(ToolNames.MigrationTool, None)
        addCMFPloneTool(ToolNames.ActionIconsTool, None)
        addCMFPloneTool(ToolNames.CalendarTool, None)

        # 3rd party tools we depend on
        addCMFPloneTool(ToolNames.QuickInstallerTool, None)
        addCMFPloneTool(ToolNames.GroupsTool, None)
        addCMFPloneTool(ToolNames.GroupDataTool, None)

    def create(self, parent, id, create_userfolder):
        id = str(id)
        portal = self.klass(id=id)
        parent._setObject(id, portal)
        p = parent._getOb(id) # Return the fully wrapped object
        self.setup(p, create_userfolder)
        self.setupPlone(p)
        return p

from Products.PageTemplates.PageTemplateFile import PageTemplateFile
manage_addSiteForm = PageTemplateFile('www/addSite', globals())
manage_addSiteForm.__name__ = 'addSite'
from Products.CMFDefault.Portal import manage_addCMFSite
def manage_addSite(self, id, title='Portal', description='',
                   create_userfolder=1,
                   email_from_address='postmaster@localhost',
                   email_from_name='Portal Administrator',
                   validate_email=0,
                   custom_policy='Default Plone',
                   RESPONSE=None):
    """ Plone Site factory """
    gen = PloneGenerator()
    p = gen.create(self, id.strip(), create_userfolder)
    gen.setupDefaultProperties(p, title, description,
                               email_from_address, email_from_name,
                               validate_email)
    customization_policy=None
    if listPolicies() and custom_policy:
        customization_policy=custom_policies[custom_policy]
        # Save customization policy results on a object
        result = customization_policy.customize(p)
        if result:
            p.invokeFactory(type_name='Document', id='CustomizationLog')
            p.CustomizationLog.edit(text_format='plain', text=result)

    # reindex catalog and workflow settings
    p.portal_catalog.refreshCatalog()
    p.portal_workflow.updateRoleMappings()

    if RESPONSE is not None:
        RESPONSE.redirect(p.absolute_url())

def register(context, globals):
    context.registerClass(meta_type='Plone Site',
                          permission='Add CMF Sites',
                          constructors=(manage_addSiteForm,
                                        manage_addSite,) )
