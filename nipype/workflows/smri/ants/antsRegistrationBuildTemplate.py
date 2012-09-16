#################################################################################
## Program:   Build Template Parallel
## Language:  Python
##
## Authors:  Jessica Forbes, Grace Murray, and Hans Johnson, University of Iowa
##
##      This software is distributed WITHOUT ANY WARRANTY; without even
##      the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
##      PURPOSE.
##
#################################################################################

import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
from nipype.interfaces.utility import Function

from nipype.interfaces.ants import (AverageImages, MultiplyImages,
                                    WarpImageMultiTransform, Registration,
                                    ApplyTransforms, AverageAffineTransform)

def GetFirstListElement(this_list):
    return this_list[0]

def MakeTransformListWithGradientWarps(averageAffineTranform, gradientStepWarp):
    return [averageAffineTranform, gradientStepWarp, gradientStepWarp, gradientStepWarp, gradientStepWarp]
def RenestDeformedPassiveImages(deformedPassiveImages,flattened_image_nametypes):
    import os
    """ Now make a list of lists of images where the outter list is per image type,
    and the inner list is the same size as the number of subjects to be averaged.
    In this case, the first element will be a list of all the deformed T2's, and
    the second element will be a list of all deformed POSTERIOR_AIR,  etc..
    """
    all_images_size=len(deformedPassiveImages)
    image_dictionary_of_lists=dict()
    nested_imagetype_list=list()
    outputAverageImageName_list=list()
    image_type_list=list()
    ## make empty_list, this is not efficient, but it works
    for name in flattened_image_nametypes:
        image_dictionary_of_lists[name]=list()
    for index in range(0,all_images_size):
        curr_name=flattened_image_nametypes[index]
        curr_file=deformedPassiveImages[index]
        image_dictionary_of_lists[curr_name].append(curr_file)
    for image_type,image_list in image_dictionary_of_lists.items():
        nested_imagetype_list.append(image_list)
        outputAverageImageName_list.append('AVG_'+image_type+'.nii.gz')
        image_type_list.append('WARP_AVG_'+image_type)
    print "\n"*10
    print "HACK: ", nested_imagetype_list
    print "HACK: ", outputAverageImageName_list
    print "HACK: ", image_type_list
    return nested_imagetype_list,outputAverageImageName_list,image_type_list

def SplitAffineAndWarpComponents(list_of_transforms_lists):
    ### Nota bene: The outputs will include the initial_moving_transform from Registration (which depends on what
    ###            the invert_initial_moving_transform is set to)
    affine_component = []
    warp_component   = []
    for transform in list_of_transforms_lists:
        affine_component.append(transform[0])
        warp_component.append(transform[1])
    print "HACK ", affine_component, " ", warp_component
    return affine_component, warp_component

## Flatten and return equal length transform and images lists.
def FlattenTransformAndImagesList(ListOfPassiveImagesDictionaries,transformation_series):
    import sys
    print("HACK:  DEBUG: ListOfPassiveImagesDictionaries\n{lpi}\n".format(lpi=ListOfPassiveImagesDictionaries))
    subjCount=len(ListOfPassiveImagesDictionaries)
    tranCount=len(transformation_series)
    if subjCount != tranCount:
        print "ERROR:  subjCount must equal tranCount {0} != {1}".format(subjCount,tranCount)
        sys.exit(-1)
    flattened_images=list()
    flattened_image_nametypes=list()
    flattened_transforms=list()
    passiveImagesCount = len(ListOfPassiveImagesDictionaries[0])
    for subjIndex in range(0,subjCount):
        #if passiveImagesCount != len(ListOfPassiveImagesDictionaries[subjIndex]):
        #    print "ERROR:  all image lengths must be equal {0} != {1}".format(passiveImagesCount,len(ListOfPassiveImagesDictionaries[subjIndex]))
        #    sys.exit(-1)
        subjImgDictionary=ListOfPassiveImagesDictionaries[subjIndex]
        subjToAtlasTransform=transformation_series[subjIndex]
        for imgname,img in subjImgDictionary.items():
            flattened_images.append(img)
            flattened_image_nametypes.append(imgname)
            flattened_transforms.append(subjToAtlasTransform)
    print("HACK: flattened images    {0}\n".format(flattened_images))
    print("HACK: flattened nametypes {0}\n".format(flattened_image_nametypes))
    print("HACK: flattened txfms     {0}\n".format(flattened_transforms))
    return flattened_images,flattened_transforms,flattened_image_nametypes
##
## NOTE:  The modes can be either 'SINGLE_IMAGE' or 'MULTI'
##        'SINGLE_IMAGE' is quick shorthand when you are building an atlas with a single subject, then registration can
##                    be short-circuted
##        any other string indicates the normal mode that you would expect and replicates the shell script build_template_parallel.sh
def antsRegistrationTemplateBuildSingleIterationWF(iterationPhasePrefix,CLUSTER_QUEUE,mode='MULTI'):

    TemplateBuildSingleIterationWF = pe.Workflow(name = 'antsRegistrationTemplateBuildSingleIterationWF_'+str(iterationPhasePrefix) )

    inputSpec = pe.Node(interface=util.IdentityInterface(fields=['images', 'fixed_image',
                'ListOfPassiveImagesDictionaries']),
                run_without_submitting=True,
                name='InputSpec')
    ## HACK: TODO: Need to move all local functions to a common untility file, or at the top of the file so that
    ##             they do not change due to re-indenting.  Otherwise re-indenting for flow control will trigger
    ##             their hash to change.
    ## HACK: TODO: REMOVE 'transforms_list' it is not used.  That will change all the hashes
    ## HACK: TODO: Need to run all python files through the code beutifiers.  It has gotten pretty ugly.
    outputSpec = pe.Node(interface=util.IdentityInterface(fields=['template','transforms_list',
                'passive_deformed_templates']),
                run_without_submitting=True,
                name='OutputSpec')

    if mode == 'SINGLE_IMAGEXX':
        ### HACK:  A more general utility that is reused should be created.
        print "HACK: DOING SINGLE_IMAGE ", mode
        TemplateBuildSingleIterationWF.connect( [ (inputSpec, outputSpec, [(('images', GetFirstListElement ), 'template')] ), ])
        ##HACK THIS DOES NOT WORK BECAUSE FILE NAMES ARE WRONG.
        TemplateBuildSingleIterationWF.connect( [ (inputSpec, outputSpec, [(('ListOfPassiveImagesDictionaries', GetFirstListElement ), 'passive_deformed_templates')] ), ])
        return TemplateBuildSingleIterationWF

    print "HACK: DOING MULTI_IMAGE ", mode
    ##import sys
    ##sys.exit(-1)



    ### NOTE MAP NODE! warp each of the original images to the provided fixed_image as the template
    BeginANTS=pe.MapNode(interface=Registration(), name = 'BeginANTS', iterfield=['moving_image'])
    many_cpu_BeginANTS_options_dictionary={'qsub_args': '-S /bin/bash -pe smp1 8-12 -l mem_free=6000M -o /dev/null -e /dev/null '+CLUSTER_QUEUE, 'overwrite': True}
    BeginANTS.plugin_args=many_cpu_BeginANTS_options_dictionary
    BeginANTS.inputs.dimension = 3
    BeginANTS.inputs.output_transform_prefix = str(iterationPhasePrefix)+'_tfm'
    BeginANTS.inputs.transforms =               ["Affine",           "SyN"]
    BeginANTS.inputs.transform_parameters =     [[1],                [0.25,3.0,0.0]]
    BeginANTS.inputs.metric =                   ['CC',               'CC']
    BeginANTS.inputs.metric_weight =            [1.0,                1.0]
    BeginANTS.inputs.radius_or_number_of_bins = [5,                  5]
    if mode == 'SINGLE_IMAGE_IMAGE':
        ## HACK:  Just short circuit time consuming step if only registering a single image.
        BeginANTS.inputs.number_of_iterations = [[1],                [1]]
    else:
        BeginANTS.inputs.number_of_iterations = [[1000, 1000, 1000], [50, 35, 15]]
    BeginANTS.inputs.use_histogram_matching =   [True,               True]
    BeginANTS.inputs.shrink_factors =           [[3,2,1],            [3,2,1]]
    BeginANTS.inputs.smoothing_sigmas =         [[0,0,0],            [0,0,0]]
    TemplateBuildSingleIterationWF.connect(inputSpec, 'images', BeginANTS, 'moving_image')
    TemplateBuildSingleIterationWF.connect(inputSpec, 'fixed_image', BeginANTS, 'fixed_image')

    ## Now transform all the images
    wimtdeformed = pe.MapNode(interface = ApplyTransforms(), name ='wimtdeformed',
                              iterfield=['transforms',
                                         'invert_transforms_flags',
                                         'reference_image'])
    TemplateBuildSingleIterationWF.connect(inputSpec, 'fixed_image', wimtdeformed, 'input_image')
    TemplateBuildSingleIterationWF.connect(inputSpec, 'images', wimtdeformed, 'reference_image')
    TemplateBuildSingleIterationWF.connect(BeginANTS, 'forward_transforms', wimtdeformed, 'transforms')
    TemplateBuildSingleIterationWF.connect(BeginANTS, 'forward_invert_flags', wimtdeformed, 'invert_transforms_flags')

    ##  Shape Update Next =====
    ## Now  Average All moving_images deformed images together to create an updated template average
    AvgDeformedImages=pe.Node(interface=AverageImages(), name='AvgDeformedImages')
    AvgDeformedImages.inputs.dimension = 3
    AvgDeformedImages.inputs.output_average_image = str(iterationPhasePrefix)+'.nii.gz'
    AvgDeformedImages.inputs.normalize = True
    TemplateBuildSingleIterationWF.connect(wimtdeformed, "output_image", AvgDeformedImages, 'images')

    ## Now get all the AffineTransorms
    SplitAffineAndWarpComponents = pe.Node(interface=util.Function(function=SplitAffineAndWarpComponents,
                                           input_names=['list_of_transforms_lists'],
                                           output_names=['affine_component', 'warp_component']),
                                           run_without_submitting=True,
                                           name="splitAffineAndWarp"
                                          )
    SplitAffineAndWarpComponents.inputs.ignore_exception = True
    TemplateBuildSingleIterationWF.connect(BeginANTS, 'forward_transforms', SplitAffineAndWarpComponents, 'list_of_transforms_lists')

    ## Now average all affine transforms together
    AvgAffineTransform = pe.Node(interface=AverageAffineTransform(), name = 'AvgAffineTransform')
    AvgAffineTransform.inputs.dimension = 3
    AvgAffineTransform.inputs.output_affine_transform = str(iterationPhasePrefix)+'Affine.mat'
    TemplateBuildSingleIterationWF.connect(SplitAffineAndWarpComponents, 'affine_component', AvgAffineTransform, 'transforms')

    ## Now average the warp fields togther
    AvgWarpImages=pe.Node(interface=AverageImages(), name='AvgWarpImages')
    AvgWarpImages.inputs.dimension = 3
    AvgWarpImages.inputs.output_average_image = str(iterationPhasePrefix)+'warp.nii.gz'
    AvgWarpImages.inputs.normalize = True
    TemplateBuildSingleIterationWF.connect(SplitAffineAndWarpComponents, 'warp_component', AvgWarpImages, 'images')

    ## Now average the images together
    ## TODO:  For now GradientStep is set to 0.25 as a hard coded default value.
    GradientStep = 0.25
    GradientStepWarpImage=pe.Node(interface=MultiplyImages(), name='GradientStepWarpImage')
    GradientStepWarpImage.inputs.dimension = 3
    GradientStepWarpImage.inputs.second_input = -1.0 * GradientStep
    GradientStepWarpImage.inputs.output_product_image = str(iterationPhasePrefix)+'warp.nii.gz'
    TemplateBuildSingleIterationWF.connect(AvgWarpImages, 'output_average_image', GradientStepWarpImage, 'first_input')

    ## Now create the new template shape based on the average of all deformed images
    UpdateTemplateShape = pe.Node(interface = WarpImageMultiTransform(), name = 'UpdateTemplateShape')
    UpdateTemplateShape.inputs.invert_affine = [1]
    TemplateBuildSingleIterationWF.connect(AvgDeformedImages, 'output_average_image', UpdateTemplateShape, 'reference_image')
    TemplateBuildSingleIterationWF.connect(AvgAffineTransform, 'affine_transform', UpdateTemplateShape, 'transformation_series')
    TemplateBuildSingleIterationWF.connect(GradientStepWarpImage, 'output_product_image', UpdateTemplateShape, 'moving_image')

    ApplyInvAverageAndFourTimesGradientStepWarpImage = pe.Node(interface=util.Function(function=MakeTransformListWithGradientWarps,
                                         input_names=['averageAffineTranform', 'gradientStepWarp'],
                                         output_names=['TransformListWithGradientWarps']),
                 run_without_submitting=True,
                 name='MakeTransformListWithGradientWarps')
    ApplyInvAverageAndFourTimesGradientStepWarpImage.inputs.ignore_exception = True

    TemplateBuildSingleIterationWF.connect(AvgAffineTransform, 'affine_transform', ApplyInvAverageAndFourTimesGradientStepWarpImage, 'averageAffineTranform')
    TemplateBuildSingleIterationWF.connect(UpdateTemplateShape, 'output_image', ApplyInvAverageAndFourTimesGradientStepWarpImage, 'gradientStepWarp')

    ReshapeAverageImageWithShapeUpdate = pe.Node(interface = WarpImageMultiTransform(), name = 'ReshapeAverageImageWithShapeUpdate')
    ReshapeAverageImageWithShapeUpdate.inputs.invert_affine = [1]
    ReshapeAverageImageWithShapeUpdate.inputs.out_postfix = '_Reshaped'
    TemplateBuildSingleIterationWF.connect(AvgDeformedImages, 'output_average_image', ReshapeAverageImageWithShapeUpdate, 'moving_image')
    TemplateBuildSingleIterationWF.connect(AvgDeformedImages, 'output_average_image', ReshapeAverageImageWithShapeUpdate, 'reference_image')
    TemplateBuildSingleIterationWF.connect(ApplyInvAverageAndFourTimesGradientStepWarpImage, 'TransformListWithGradientWarps', ReshapeAverageImageWithShapeUpdate, 'transformation_series')
    TemplateBuildSingleIterationWF.connect(ReshapeAverageImageWithShapeUpdate, 'output_image', outputSpec, 'template')

    ######
    ######
    ######  Process all the passive deformed images in a way similar to the main image used for registration
    ######
    ######
    ######
    ##############################################
    ## Now warp all the ListOfPassiveImagesDictionaries images
    FlattenTransformAndImagesListNode = pe.Node( Function(function=FlattenTransformAndImagesList,
                                  input_names = ['ListOfPassiveImagesDictionaries','transformation_series'],
                                  output_names = ['flattened_images','flattened_transforms','flattened_image_nametypes']),
                                  run_without_submitting=True, name="99_FlattenTransformAndImagesList")
    TemplateBuildSingleIterationWF.connect( inputSpec,'ListOfPassiveImagesDictionaries', FlattenTransformAndImagesListNode, 'ListOfPassiveImagesDictionaries' )
    TemplateBuildSingleIterationWF.connect( BeginANTS,'forward_transforms', FlattenTransformAndImagesListNode, 'transformation_series' )
    wimtPassivedeformed = pe.MapNode(interface = WarpImageMultiTransform(),
                     iterfield=['transformation_series', 'moving_image'],
                     name ='wimtPassivedeformed')
    TemplateBuildSingleIterationWF.connect(FlattenTransformAndImagesListNode, 'flattened_images',     wimtPassivedeformed, 'moving_image')
    TemplateBuildSingleIterationWF.connect(FlattenTransformAndImagesListNode, 'flattened_transforms', wimtPassivedeformed, 'transformation_series')

    RenestDeformedPassiveImagesNode = pe.Node( Function(function=RenestDeformedPassiveImages,
                                  input_names = ['deformedPassiveImages','flattened_image_nametypes'],
                                  output_names = ['nested_imagetype_list','outputAverageImageName_list','image_type_list']),
                                  run_without_submitting=True, name="99_RenestDeformedPassiveImages")
    TemplateBuildSingleIterationWF.connect(wimtPassivedeformed, 'output_image', RenestDeformedPassiveImagesNode, 'deformedPassiveImages')
    TemplateBuildSingleIterationWF.connect(FlattenTransformAndImagesListNode, 'flattened_image_nametypes', RenestDeformedPassiveImagesNode, 'flattened_image_nametypes')
    ## Now  Average All passive moving_images deformed images together to create an updated template average
    AvgDeformedPassiveImages=pe.MapNode(interface=AverageImages(),
      iterfield=['images','output_average_image'],
      name='AvgDeformedPassiveImages')
    AvgDeformedPassiveImages.inputs.dimension = 3
    AvgDeformedPassiveImages.inputs.normalize = False
    TemplateBuildSingleIterationWF.connect(RenestDeformedPassiveImagesNode, "nested_imagetype_list", AvgDeformedPassiveImages, 'images')
    TemplateBuildSingleIterationWF.connect(RenestDeformedPassiveImagesNode, "outputAverageImageName_list", AvgDeformedPassiveImages, 'output_average_image')

    ## -- TODO:  Now neeed to reshape all the passive images as well
    ReshapeAveragePassiveImageWithShapeUpdate = pe.MapNode(interface = WarpImageMultiTransform(),
      iterfield=['moving_image','reference_image','out_postfix'],
      name = 'ReshapeAveragePassiveImageWithShapeUpdate')
    ReshapeAveragePassiveImageWithShapeUpdate.inputs.invert_affine = [1]
    TemplateBuildSingleIterationWF.connect(RenestDeformedPassiveImagesNode, "image_type_list", ReshapeAveragePassiveImageWithShapeUpdate, 'out_postfix')
    TemplateBuildSingleIterationWF.connect(AvgDeformedPassiveImages, 'output_average_image', ReshapeAveragePassiveImageWithShapeUpdate, 'moving_image')
    TemplateBuildSingleIterationWF.connect(AvgDeformedPassiveImages, 'output_average_image', ReshapeAveragePassiveImageWithShapeUpdate, 'reference_image')
    TemplateBuildSingleIterationWF.connect(ApplyInvAverageAndFourTimesGradientStepWarpImage, 'TransformListWithGradientWarps', ReshapeAveragePassiveImageWithShapeUpdate, 'transformation_series')
    TemplateBuildSingleIterationWF.connect(ReshapeAveragePassiveImageWithShapeUpdate, 'output_image', outputSpec, 'passive_deformed_templates')

    return TemplateBuildSingleIterationWF